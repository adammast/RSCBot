import ast
import asyncio
import difflib
import re

import discord
from discord.ext.commands import Context
from playerRatings import PlayerRatings
from prefixManager import PrefixManager
from redbot.core import Config, checks, commands
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

defaults = {"Tiers": [], "Teams": [], "Team_Roles": {}}

class TeamManager(commands.Cog):
    """Used to match roles to teams"""

    FRANCHISE_ROLE_KEY = "Franchise Role"
    TIER_ROLE_KEY = "Tier Role"
    GM_ROLE = "General Manager"
    CAPTAN_ROLE = "Captain"
    IR_ROLE = "IR"
    PERM_FA_ROLE = "PermFA"
    SUBBED_OUT_ROLE = "Subbed Out"
    VERIFY_TIMEOUT = 30                     #seconds

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567892, force_registration=True)
        self.config.register_guild(**defaults)
        self.prefix_cog: PrefixManager = bot.get_cog("PrefixManager")

#region commmands

    #region franchise commands

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def addFranchise(self, ctx: Context, gm: discord.Member, franchise_prefix: str, *, franchise_name: str):
        """Add a single franchise and prefix
        This will also create the franchise role in the format: <franchise name> (GM name)
        Afterwards it will assign this role and the General Manager role to the new GM and modify their nickname
        
        Examples:
        [p]addFranchise nullidea MEC Mechanics
        [p]addFranchise adammast OCE The Ocean
        [p]addFranchise Drupenson POA Planet of the Apes
        """
        
        prompt = "Franchise Name: **{franchise}**\nPrefix: **{prefix}**\nGeneral Manager: **{gm}**\n\nAre you sure you want to add this franchise?".format(
            franchise=franchise_name, prefix=franchise_prefix, gm=gm.name)
        nvm_msg = "No changes made."

        if not await self._react_prompt(ctx, prompt, nvm_msg):
            return False

        gm_role = self._find_role_by_name(ctx, TeamManager.GM_ROLE)
        franchise_role_name = "{0} ({1})".format(franchise_name, gm.name)
        franchise_role = await self._create_role(ctx, franchise_role_name)

        if franchise_role and not self.is_gm(gm):
            await gm.add_roles(gm_role, franchise_role)
            await self.prefix_cog.add_prefix(ctx, gm.name, franchise_prefix)
            await self.set_member_nickname_prefix(ctx, franchise_prefix, gm)
            await ctx.send("Done.")
        else:
            if self.is_gm(gm):
                await ctx.send("{0} is already a General Manager.".format(gm.name))
            await ctx.send("Franchise was not created.")

    @commands.command()
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def removeFranchise(self, ctx: Context, *, franchise_identifier: str):
        """Removes a franchise and all of its components (role, prefix) from the league.
        A franchise must not have any teams for this command to work.
        
        Examples:
        \t[p]removeFranchise adammast
        \t[p]removeFranchise OCE
        \t[p]removeFranchise The Ocean"""
        franchise_data = await self._get_franchise_data(ctx, franchise_identifier)
        if not franchise_data:
            await ctx.send("No franchise could be found with the identifier: **{0}**".format(franchise_identifier))
            return False

        franchise_role, gm_name, franchise_prefix, franchise_name = franchise_data
        gm = self._find_member_by_name(ctx, gm_name) # get gm member type from gm string

        prompt = "Franchise Name: **{franchise}**\nPrefix: **{prefix}**\nGeneral Manager: **{gm}**\n\nAre you sure you want to remove this franchise?".format(
            franchise=franchise_name, prefix=franchise_prefix, gm=gm_name)
        nvm_msg = "No changes made."

        if not await self._react_prompt(ctx, prompt, nvm_msg):
            return False
        
        gm_active = gm in ctx.guild.members
        franchise_role = self._get_franchise_role(ctx, gm.name)
        franchise_teams = await self._find_teams_for_franchise(ctx, franchise_role)
        if len(franchise_teams) > 0:
            await ctx.send(":x: Cannot remove a franchise that has teams enrolled.")
        else:
            gm_role = self._find_role_by_name(ctx, TeamManager.GM_ROLE)
            if gm_active:
                await gm.remove_roles(gm_role)
            await franchise_role.delete()
            await self.prefix_cog.remove_prefix(ctx, gm_name)
            await self.set_member_nickname_prefix(ctx, None, gm)
            await ctx.send("Done.")

    @commands.command(aliases=["recoverFranchise", "claimFranchise"])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def transferFranchise(self, ctx: Context, new_gm: discord.Member, *, franchise_identifier: str):
        """Transfer ownership of a franchise to a new GM, with the franchise's name, prefix, or previous GM.
        
        Examples:
        \t[p]transferFranchise nullidea adammast
        \t[p]recoverFranchise nullidea The Ocean
        \t[p]claimFranchise nullidea OCE"""

        if self.is_gm(new_gm):
            await ctx.send("{0} already has the \"General Manager\" role.".format(new_gm.name))
            return False

        franchise_data = await self._get_franchise_data(ctx, franchise_identifier)
        if not franchise_data:
            await ctx.send("No franchise could be found with the identifier: **{0}**".format(franchise_identifier))
            return False

        franchise_role, old_gm_name, franchise_prefix, franchise_name = franchise_data
        
        prompt = "Transfer ownership of **{franchise}** from {old_gm} to {new_gm}?".format(
            franchise=franchise_name, old_gm=old_gm_name, new_gm=new_gm.name)
        nvm_msg = "No changes made."

        if not await self._react_prompt(ctx, prompt, nvm_msg):
            return False

        ## TRANSFER/RECOVER FRANCHISE
        
        # rename franchise role
        franchise_name = self.get_franchise_name_from_role(franchise_role)
        new_franchise_name = "{0} ({1})".format(franchise_name, new_gm.name)
        await franchise_role.edit(name=new_franchise_name)

        # change prefix association to new GM
        await self.prefix_cog.remove_prefix(ctx, old_gm_name)
        await self.prefix_cog.add_prefix(ctx, new_gm.name, franchise_prefix)
        await self.set_member_nickname_prefix(ctx, franchise_prefix, new_gm)

        # reassign roles for gm/franchise
        franchise_tier_roles = await self._find_franchise_tier_roles(ctx, franchise_role)
        gm_role = self._find_role_by_name(ctx, TeamManager.GM_ROLE)
        transfer_roles = [gm_role, franchise_role]
        await new_gm.add_roles(*transfer_roles)

        # If old GM is still in server:
        old_gm = self._find_member_by_name(ctx, old_gm_name)
        if old_gm:
            await old_gm.remove_roles(*transfer_roles)
            await self.set_member_nickname_prefix(ctx, "", old_gm)
            former_gm_role = self._find_role_by_name(ctx, "Former GM")
            if former_gm_role:
                await old_gm.add_roles(former_gm_role)
            
        
        await ctx.send("{0} is the new General Manager for {1}.".format(new_gm.name, franchise_name))
    
    @commands.command(aliases=["getFranchises", "listFranchises"])
    @commands.guild_only()
    async def franchises(self, ctx: Context):
        """Provides a list of all the franchises set up in the server 
        including the name of the GM for each franchise"""
        franchise_roles = self._get_all_franchise_roles(ctx)
        embed = discord.Embed(title="Franchises:", color=discord.Colour.blue(), 
            description="{}".format("\n".join([role.name for role in franchise_roles])), thumbnail=ctx.guild.icon_url)
        await ctx.send(embed=embed)

    #endregion

    #region tier commands

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def addTier(self, ctx: Context, tier_name: str):
        """Add a tier to the tier list and creates corresponding roles. 
        This will need to be done before any transactions can be done for players in this tier"""
        await self._create_role(ctx, tier_name)
        await self._create_role(ctx, "{0}FA".format(tier_name))
        tiers = await self._tiers(ctx.guild)
        tiers.append(tier_name)
        await self._save_tiers(ctx.guild, tiers)
        await ctx.send("Done.")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def removeTier(self, ctx: Context, tier_name: str):
        """Remove a tier from the tier list and the tier's corresponding roles"""
        removed = await self._remove_tier(ctx, tier_name)
        if removed:
            await ctx.send("Done.")
        else:
            await ctx.send(":x: Cannot remove a tier that has teams enrolled.")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def removeAllTiers(self, ctx: Context):
        """Removes all tiers and corresponding roles from the server"""
        # we need tiers
        tiers = await self._tiers(ctx.guild)

        removed = []
        not_removed = []
        for tier in tiers:
            if await self._remove_tier(ctx, tier):
                removed.append(tier)
            else:
                not_removed.append(tier)

        if not_removed:
            message = ":white_check_mark: The following tiers have been removed: {0}".format(', '.join(removed))
            message += "\n:x: The following tiers could not be removed: {0}".format(', '.join(not_removed))
            await ctx.send(message)
        else:
            await ctx.send("Removed {} tiers.".format(len(removed)))

    @commands.command(aliases=["tiers", "getTiers"])
    @commands.guild_only()
    async def listTiers(self, ctx: Context):
        """Provides a list of all the tiers set up in the server"""
        tiers = await self._tiers(ctx.guild)
        if tiers:
            await ctx.send(
                "Tiers set up in this server: {0}".format(", ".join(tiers)))
        else:
            await ctx.send("No tiers set up in this server.")

    #endregion

    #region team commands

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def addTeams(self, ctx: Context, *teams_to_add):
        """Add the teams provided to the team list.

        Arguments:

        teams_to_add -- One or more teams in the following format:
        ```
        "['<team_name>','<gm_name>','<tier>']"
        ```
        Each team should be separated by a space.

        Examples:
        ```
        [p]addTeams "['Derechos','Shamu','Challenger']"
        [p]addTeams "['Derechos','Shamu','Challenger']" "['Barbarians','Snipe','Challenger']"
        ```
        """
        addedCount = 0
        try:
            for teamStr in teams_to_add:
                team = ast.literal_eval(teamStr)
                teamAdded = await self._add_team(ctx, *team)
                if teamAdded:
                    addedCount += 1
        finally:
            await ctx.send("Added {0} team(s).".format(addedCount))
        await ctx.send("Done.")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def addTeam(self, ctx: Context, team_name: str, gm_name: str, tier: str):
        """Add a single team and it's corresponding roles to the file system to be used for transactions and match info"""
        teamAdded = await self._add_team(ctx, team_name, gm_name, tier)
        if(teamAdded):
            await ctx.send("Done.")
        else:
            await ctx.send("Error adding team: {0}".format(team_name))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def removeTeam(self, ctx: Context, *, team_name: str):
        """Removes team from the file system. Team roles will be cleared as well"""
        teamRemoved = await self._remove_team(ctx, team_name)
        if teamRemoved:
            await ctx.send("Done.")
        else:
            await ctx.send("Error removing team: {0}".format(team_name))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearTeams(self, ctx: Context):
        """Removes all teams from the file system. Team roles will be cleared as well"""
        teams = await self._teams(ctx.guild)
        team_roles = await self._team_roles(ctx.guild)

        teams.clear()
        team_roles.clear()
        
        await self._save_teams(ctx.guild, teams)
        await self._save_team_roles(ctx.guild, team_roles)
        await ctx.send("Done.")
    
    @commands.command()
    @commands.guild_only()
    async def teams(self, ctx: Context, *, franchise_tier_prefix: str):
        """Returns a list of teams based on the input. 
        You can either give it the name of a franchise, a tier, or the prefix for a franchise.
        
        Examples:
        \t[p]teams The Ocean
        \t[p]teams Challenger
        \t[p]teams OCE"""
        # Prefix
        prefixes = await self.prefix_cog._prefixes(ctx.guild)
        if(len(prefixes.items()) > 0):
            for key, value in prefixes.items():
                if franchise_tier_prefix.casefold() == value.casefold():
                    gm_name = key
                    franchise_role = self._get_franchise_role(ctx, gm_name)
                    await ctx.send(embed=await self._format_teams_for_franchise(ctx, franchise_role))
                    return

        # Tier
        tiers = await self._tiers(ctx.guild)
        for tier in tiers:
            if tier.casefold() == franchise_tier_prefix.casefold():
                await ctx.send(embed=await self._format_teams_for_tier(ctx, tier))
                return

        # Franchise name
        franchise_role = self.get_franchise_role_from_name(ctx.guild, franchise_tier_prefix)
        if franchise_role is not None:
            await ctx.send(embed=await self._format_teams_for_franchise(ctx, franchise_role))
        else:
            await ctx.send("No franchise, tier, or prefix with name: {0}".format(franchise_tier_prefix))

    @commands.command(aliases=["getTeams"])
    @commands.guild_only()
    async def listTeams(self, ctx: Context):
        """Provides a list of all the teams set up in the server"""
        teams = await self._teams(ctx.guild)
        if teams:
            messages = []
            message = "Teams set up in this server: "
            for team in teams:
                message += "\n{0}".format(team)
                if len(message) > 1900:
                    messages.append(message)
                    message = ""
            if message:
                messages.append(message)
            for msg in messages:
                await ctx.send("{0}{1}{0}".format("```", msg))
        else:
            await ctx.send("No teams set up in this server.")

    @commands.command()
    @commands.guild_only()
    async def teamRoles(self, ctx: Context, team_name: str):
        """Prints out the franchise and tier role that corresponds with the given team"""
        franchise_role, tier_role = await self.get_roles_for_team(ctx.guild, team_name)
        if franchise_role and tier_role:
            await ctx.send(
                    "Franchise role for {0} = {1}\nTier role for {0} = {2}".format(team_name, franchise_role.name, tier_role.name))
        else:
            await ctx.send("No franchise and tier roles set up for {0}".format(team_name))

    #endregion

    @commands.command()
    @commands.guild_only()
    async def roster(self, ctx: Context, *, team_name: str):
        """Shows all the members associated with a team including the GM"""
        team, found = await self.match_team_name(ctx.guild, team_name)
        if found:
            franchise_role, tier_role = await self.get_roles_for_team(ctx.guild, team)
            if franchise_role is None or tier_role is None:
                await ctx.send("No franchise and tier roles set up for {0}".format(team))
                return
            await ctx.send(embed=await self.embed_roster(ctx, team))
        else:
            message = "No team with name: {0}".format(team_name)
            if len(team) > 0:
                message += "\nDo you mean one of these teams:"
                for possible_team in team:
                    message += " `{0}`".format(possible_team)
            await ctx.send(message)

    @commands.command(aliases=["captain", "cptn", "cptns"])
    @commands.guild_only()
    async def captains(self, ctx: Context, *, franchise_tier_prefix: str):
        """Returns a list of team captains under a tier or franchise based on the input. 
        You can either give it the name of a tier, or a franchise identifier (prefix, name, or GM name).
        
        Examples:
        \t[p]captains The Ocean
        \t[p]captains Challenger
        \t[p]captains OCE"""

        found = False
        # Prefix
        prefixes = await self.prefix_cog._prefixes(ctx.guild)
        if(len(prefixes.items()) > 0):
            for key, value in prefixes.items():
                if franchise_tier_prefix.casefold() == value.casefold() or franchise_tier_prefix.casefold() == key.casefold():
                    gm_name = key
                    franchise_role = self._get_franchise_role(ctx, gm_name)
                    found = True
        
        # Franchise name
        if not found:
            franchise_role = self.get_franchise_role_from_name(ctx.guild, franchise_tier_prefix)
            if franchise_role is not None:
                found = True
        
        # find captains for franchise by franchise role
        if found:
            await ctx.send(embed=await self.embed_franchise_captains(ctx, franchise_role))
            return

        # Tier
        tiers = await self._tiers(ctx.guild)
        for tier in tiers:
            if tier.casefold() == franchise_tier_prefix.casefold():
                found = True
                await ctx.send(embed=await self.embed_tier_captains(ctx, tier))
                return
        
        await ctx.send("No franchise, tier, or prefix with name: {0}".format(franchise_tier_prefix))

    @commands.command(aliases=["fa", "fas"])
    @commands.guild_only()
    async def freeAgents(self, ctx: Context, tier: str, filter=None):
        """
        Gets a list of all free agents in a specific tier
         - Filters for PermFA: perm, permfa, restricted, p, r, rfa, permanent
         - Filters for signable FAs: non-perm, unrestricted, u, ufa, signable
        """
        tiers = await self._tiers(ctx.guild)
        tier_name = None
        for _tier in tiers:
            if tier.casefold() == _tier.casefold():
                tier_name = _tier
                break
        
        perm_fa_filters = ['perm', 'permfa', 'restricted', 'p', 'r', 'rfa', 'permanent']
        signable_fa_filters = ['nonperm', 'non-perm', 'unrestricted', 'u', 'ufa', 'signable']
        
        if tier_name is None:
            await ctx.send("No tier with name: {0}".format(tier))
            return

        fa_role = self._find_role_by_name(ctx, tier_name + "FA")
        if fa_role is None:
            await ctx.send("No free agent role with name: {0}".format(tier_name + "FA"))
            return

        perm_fa_role = self._find_role_by_name(ctx, self.PERM_FA_ROLE)

        message = "```"
        for member in ctx.message.guild.members:
            if fa_role in member.roles:
                if filter: # Optional filter for PermFA and signable FAs
                    if filter.casefold() in perm_fa_filters:
                        if perm_fa_role is not None and perm_fa_role in member.roles:
                            message += "\n{0} {1}".format(member.display_name, ("(Permanent FA)"))
                    elif filter.casefold() in signable_fa_filters:
                        if perm_fa_role is not None and perm_fa_role not in member.roles:
                            message += "\n{0}".format(member.display_name)
                else:
                    message += "\n{0}".format(member.display_name)
                    if perm_fa_role is not None and perm_fa_role in member.roles:
                        message += " (Permanent FA)"
        message += "```"

        color = discord.Colour.blue()
        for role in ctx.guild.roles:
            if role.name.casefold() == tier_name.casefold():
                color = role.color
        embed = discord.Embed(title="{0} Free Agents:".format(tier_name), color=color, 
            description=message, thumbnail=ctx.guild.icon_url)
                    
        await ctx.send(embed=embed)

#endregion

#region helper methods

    async def _react_prompt(self, ctx: Context, prompt, if_not_msg=None):
        user = ctx.message.author
        react_msg = await ctx.send(prompt)
        start_adding_reactions(react_msg, ReactionPredicate.YES_OR_NO_EMOJIS)
        try:
            pred = ReactionPredicate.yes_or_no(react_msg, user)
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=self.VERIFY_TIMEOUT)
            if pred.result:
                return True
            if if_not_msg:
                await ctx.send(if_not_msg)
            return False
        except asyncio.TimeoutError:
            await ctx.send("Sorry {}, you didn't react quick enough. Please try again.".format(user.mention))
            return False

    async def _get_franchise_data(self, ctx: Context, franchise_identifier):
        franchise_found = False
        # GM/Prefix Identifier
        prefixes = await self.prefix_cog._prefixes(ctx.guild)
        if(len(prefixes.items()) > 0):
            for key, value in prefixes.items():
                if franchise_identifier.casefold() == key.casefold() or franchise_identifier.casefold() == value.casefold():
                    franchise_found = True
                    gm_name = key
                    franchise_prefix = value
                    franchise_role = self._get_franchise_role(ctx, gm_name)
                    franchise_name = self.get_franchise_name_from_role(franchise_role)
                    
                
        # Franchise name identifier
        if not franchise_found:
            franchise_role = self.get_franchise_role_from_name(ctx.guild, franchise_identifier)
            if franchise_role:
                franchise_found = True
                franchise_name = self.get_franchise_name_from_role(franchise_role)
                gm_name = self.get_gm_name_from_franchise_role(franchise_role)
                franchise_prefix = await self.prefix_cog.get_gm_prefix(ctx.guild, gm_name)

        if franchise_found:
            return franchise_role, gm_name, franchise_prefix, franchise_name
        return None

    def is_gm(self, member):
        for role in member.roles:
            if role.name == self.GM_ROLE:
                return True
        return False

    def is_captain(self, member):
        for role in member.roles:
            if role.name == self.CAPTAN_ROLE:
                return True
        return False

    def is_IR(self, member):
        for role in member.roles:
            if role.name == self.IR_ROLE:
                return True
        return False

    def is_subbed_out(self, member):
        for role in member.roles:
            if role.name == self.SUBBED_OUT_ROLE:
                return True
        return False

    async def teams_for_user(self, ctx: Context, user):
        franchise_role = self.get_current_franchise_role(user)
        if self.is_gm(user):
            return await self._find_teams_for_franchise(ctx, franchise_role)
        tiers = await self._tiers(ctx.guild)
        teams = []
        for role in user.roles:
            if role.name in tiers:
                tier_role = role
                team_name = await self._find_team_name(ctx, franchise_role, tier_role)
                teams.append(team_name)
        return teams

    def members_from_team(self, ctx: Context, franchise_role, tier_role):
        """Retrieve the list of all users that are on the team
        indicated by the provided franchise_role and tier_role.
        """
        team_members = []
        for member in ctx.message.guild.members:
            if franchise_role in member.roles:
                if tier_role in member.roles:
                    team_members.append(member)
        return team_members

    async def _get_team_captain(self, ctx: Context, franchise_role: discord.Role, tier_role: discord.Role):
        captain_role = self._find_role_by_name(ctx, "Captain")
        members = self.members_from_team(ctx, franchise_role, tier_role)
        for member in members:
            if captain_role in member.roles:
                return member
        return None
            
    async def _create_role(self, ctx: Context, role_name: str):
        """Creates and returns a new Guild Role"""
        for role in ctx.guild.roles:
            if role.name == role_name:
                await ctx.send("The role \"{0}\" already exists in the server.".format(role_name))
                return None
        return await ctx.guild.create_role(name=role_name)

    async def _format_team_member_for_message(self, ctx: Context, member, *args):
        extraRoles = list(args)
        if self.is_gm(member):
            extraRoles.insert(0, "GM")
        if self.is_IR(member):
            extraRoles.append("IR")
        roleString = ""
        if extraRoles:
            roleString = " ({0})".format("|".join(extraRoles))
        recordString = ""
        try:
            player_ratings: PlayerRatings = self.bot.get_cog("PlayerRatings")
            wins, losses, rating = await player_ratings.get_player_record_and_rating_by_id(ctx.guild, member.id)
            if wins is not None:
                recordString = " ({0}-{1}, {2})".format(wins, losses, rating)
        except:
            pass
        return "{0}{1}{2}".format(member.display_name, recordString, roleString)

    async def _format_teams_for_franchise(self, ctx: Context, franchise_role):
        teams = await self._find_teams_for_franchise(ctx, franchise_role)
        teams_message = ""
        for team in teams:
            tier_role = (await self.get_roles_for_team(ctx.guild, team))[1]
            teams_message += "\n\t{0} ({1})".format(team, tier_role.name)

        embed = discord.Embed(title="{0}:".format(franchise_role.name), color=discord.Colour.blue(), description=teams_message)
        emoji = await self.get_franchise_emoji(ctx.guild, franchise_role)
        if(emoji):
            embed.set_thumbnail(url=emoji.url)
        return embed

    async def _format_teams_for_tier(self, ctx: Context, tier):
        teams = await self.get_teams_for_tier(ctx.guild, tier)
        teams_message = ""
        for team in teams:
            franchise_role = (await self.get_roles_for_team(ctx.guild, team))[0]
            gmNameFromRole = re.findall(r'(?<=\().*(?=\))', franchise_role.name)[0]
            teams_message += "\n\t{0} ({1})".format(team, gmNameFromRole)

        color = discord.Colour.blue()
        for role in ctx.guild.roles:
            if role.name.casefold() == tier.casefold():
                color = role.color

        embed = discord.Embed(title="{0} teams:".format(tier), color=color, description=teams_message)
        return embed

    async def _remove_tier(self, ctx: Context, tier_name):
        if len(await self.get_teams_for_tier(ctx.guild, tier_name)) > 0:
            return False
        else:
            tier_role = self._get_tier_role(ctx, tier_name)
            tier_fa_role = self._find_role_by_name(ctx, "{0}FA".format(tier_name))
            if tier_role:
                await tier_role.delete()
            if tier_fa_role:
                await tier_fa_role.delete()
            tiers = await self._tiers(ctx.guild)
            try:
                tiers.remove(tier_name)
            except ValueError:
                await ctx.send(
                    "{0} does not seem to be a tier.".format(tier_name))
                return
            await self._save_tiers(ctx.guild, tiers)
            return True

    def _extract_tier_from_role(self, team_role):
        tier_matches = re.findall(r'\w*\b(?=\))', team_role.name)
        return None if not tier_matches else tier_matches[0]

    def _extract_franchise_name_from_role(self, franchise_role: discord.Role):
        franchise_name_gm = franchise_role.name
        franchise_name = franchise_name_gm[:franchise_name_gm.index(" (")]
        return franchise_name
    
    async def _add_team(self, ctx: Context, team_name: str, gm_name: str, tier: str):
        teams = await self._teams(ctx.guild)
        team_roles = await self._team_roles(ctx.guild)

        tier_role = self._get_tier_role(ctx, tier)

        franchise_role = self._get_franchise_role(ctx, gm_name)

        # Validation of input
        # There are other validations we could do, but don't
        #     - that there aren't extra args
        errors = []
        if not team_name:
            errors.append("Team name not found.")
        if not gm_name:
            errors.append("GM name not found.")
        if not tier_role:
            errors.append("Tier role not found.")
        if not franchise_role:
            errors.append("Franchise role not found.")
        if errors:
            await ctx.send(":x: Errors with input:\n\n  "
                               "* {0}\n".format("\n  * ".join(errors)))
            return

        try:
            teams.append(team_name)
            team_data = team_roles.setdefault(team_name, {})
            team_data["Franchise Role"] = franchise_role.id
            team_data["Tier Role"] = tier_role.id
        except:
            return False
        await self._save_teams(ctx.guild, teams)
        await self._save_team_roles(ctx.guild, team_roles)
        return True
    
    async def _remove_team(self, ctx: Context, team_name: str):
        franchise_role, tier_role = await self.get_roles_for_team(ctx.guild, team_name)
        teams = await self._teams(ctx.guild)
        team_roles = await self._team_roles(ctx.guild)
        try:
            teams.remove(team_name)
            del team_roles[team_name]
        except ValueError:
            await ctx.send("{0} does not seem to be a team.".format(team_name))
            return False
        await self._save_teams(ctx.guild, teams)
        await self._save_team_roles(ctx.guild, team_roles)
        gm = self.get_gm_by_franchise_role(ctx.guild, franchise_role)
        return True

    def _get_tier_role(self, ctx: Context, tier: str):
        roles = ctx.message.guild.roles
        for role in roles:
            if role.name.casefold() == tier.casefold():
                return role
        return None

    def _find_role(self, ctx: Context, role_id):
        for role in ctx.message.guild.roles:
            if role.id == role_id:
                return role
        raise LookupError('No role with id: {0} found in server roles'.format(role_id))

    def _find_role_by_name(self, ctx: Context, role_name):
        for role in ctx.message.guild.roles:
            if role.name.casefold() == role_name.casefold():
                return role
        return None

    def _find_member_by_name(self, ctx: Context, member_name: str):
        for member in ctx.guild.members:
            if member.name == member_name:
                return member
        return None
    
    def _get_franchise_role(self, ctx: Context, gm_name):
        for role in ctx.message.guild.roles:
            try:
                gmNameFromRole = re.findall(r'(?<=\().*(?=\))', role.name)[0]
                if gmNameFromRole == gm_name:
                    return role
            except:
                continue

    def _get_all_franchise_roles(self, ctx: Context):
        franchise_roles = []
        for role in ctx.message.guild.roles:
            try:
                gmNameFromRole = re.findall(r'(?<=\().*(?=\))', role.name)[0]
                if gmNameFromRole is not None:
                    franchise_roles.append(role)
            except:
                continue
        return franchise_roles

    async def get_roles_for_team(self, guild: discord.Guild, team_name: str):
        teams = await self._teams(guild)
        if teams and team_name in teams:
            team_roles = await self._team_roles(guild)
            team_data = team_roles.setdefault(team_name, {})
            franchise_role_id = team_data["Franchise Role"]
            tier_role_id = team_data["Tier Role"]
            franchise_role = guild.get_role(franchise_role_id)
            tier_role = guild.get_role(tier_role_id)
            return (franchise_role, tier_role)
        else:
           raise LookupError('No team with name: {0}'.format(team_name))

    async def _find_team_name(self, ctx: Context, franchise_role, tier_role):
        teams = await self._teams(ctx.guild)
        for team in teams:
            if await self.get_roles_for_team(ctx.guild, team) == (franchise_role, tier_role):
                return team

    async def _find_teams_for_franchise(self, ctx: Context, franchise_role):
        franchise_teams = []
        teams = await self._teams(ctx.guild)
        for team in teams:
            if (await self.get_roles_for_team(ctx.guild, team))[0] == franchise_role:
                franchise_teams.append(team)
        return franchise_teams

    async def _find_franchise_tier_roles(self, ctx: Context, franchise_role: discord.Role):
        franchise_tier_roles = []
        teams = await self._teams(ctx.guild)
        for team in teams:
            if (await self.get_roles_for_team(ctx.guild, team))[0] == franchise_role:
                tier_role = (await self.get_roles_for_team(ctx.guild, team))[1]
                franchise_tier_roles.append(tier_role)
        return franchise_tier_roles

    async def _get_franchise_tier_team(self, ctx: Context, franchise_role: discord.Role, tier_role: discord.Role):
        teams = await self._teams(ctx.guild)
        for team in teams:
            if (await self.get_roles_for_team(ctx.guild, team)) == (franchise_role, tier_role):
                return team
        return None
    
    def get_current_franchise_role(self, user: discord.Member):
        for role in user.roles:
            try:
                gmNameFromRole = re.findall(r'(?<=\().*(?=\))', role.name)[0]
                if gmNameFromRole:
                    return role
            except:
                continue

    async def get_current_tier_role(self, ctx: Context, user: discord.Member):
        tierList = await self._tiers(ctx.guild)
        for role in user.roles:
            if role.name in tierList:
                return role
        return None

    async def get_current_team_name(self, ctx: Context, user: discord.Member):
        tier_role = await self.get_current_tier_role(ctx, user)
        franchise_role = self.get_current_franchise_role(user)
        return await self._find_team_name(ctx, franchise_role, tier_role)

    def get_player_nickname(self, user: discord.Member):
        if user.nick is not None:
            array = user.nick.split(' | ', 1)
            if len(array) == 2:
                currentNickname = array[1].strip()
            else:
                currentNickname = array[0]
            return currentNickname
        return user.name

    async def set_member_nickname_prefix(self, ctx: Context, prefix: str, member: discord.member):
        try:
            if prefix:
                await member.edit(nick="{0} | {1}".format(prefix, self.get_player_nickname(member)))
            else:
                await member.edit(nick=self.get_player_nickname(member))
        except discord.Forbidden:
            await ctx.send("Changing nickname forbidden for user: {0}".format(member.name))

    def get_franchise_role_from_name(self, guild: discord.Guild, franchise_name: str):
        for role in guild.roles:
            try:
                matchedString = re.findall(r'.+?(?= \()', role.name)[0]
                if matchedString.casefold() == franchise_name.casefold():
                    return role
            except:
                continue

    def get_franchise_name_from_role(self, franchise_role: discord.Role):
        end_of_name = franchise_role.name.rindex("(") - 1
        return franchise_role.name[0:end_of_name]

    async def match_team_name(self, guild: discord.Guild, team_name):
        teams = await self._teams(guild)
        for team in teams:
            if team_name.casefold() == team.casefold():
                return team, True
        return difflib.get_close_matches(team_name, teams, n=3, cutoff=0.4), False

    async def match_tier_name(self, guild: discord.Guild, tier_name):
        tiers = await self._tiers(guild)
        for tier in tiers:
            if tier_name.casefold() == tier.casefold():
                return tier
        close_match = difflib.get_close_matches(tier_name, tiers, n=1, cutoff=0.6)
        if len(close_match) > 0:
            return close_match[0]
        return None

    async def get_teams_for_tier(self, guild: discord.Guild, tier_name):
        teams_in_tier = []
        teams = await self._teams(guild)
        for team in teams:
            team_tier = (await self.get_roles_for_team(guild, team))[1]
            if team_tier.name.casefold() == tier_name.casefold():
                teams_in_tier.append(team)
        return teams_in_tier

    async def get_franchise_emoji(self, guild: discord.Guild, franchise_role: discord.Role):
        prefix = await self.prefix_cog.get_franchise_prefix(guild, franchise_role)
        gm_name = self.get_gm_name_from_franchise_role(franchise_role)
        if prefix:
            emojis = guild.emojis
            for emoji in emojis:
                if emoji.name.casefold() == prefix.casefold() or emoji.name.casefold() == gm_name.casefold():
                    return emoji

    def get_gm_by_franchise_role(self, guild: discord.Guild, franchise_role: discord.Role):
        for member in guild.members:
            if self.is_gm(member) and franchise_role in member.roles:
                return member
        
    def get_gm_name_from_franchise_role(self, franchise_role: discord.Role):
        try:
            return re.findall(r'(?<=\().*(?=\))', franchise_role.name)[0]
        except:
            raise LookupError('GM name not found from role {0}'.format(franchise_role.name))
    
    async def get_active_members_by_team_name(self, ctx: Context, team_name):
        franchise_role, tier_role = await self.get_roles_for_team(ctx.guild, team_name)
        team_members = self.members_from_team(ctx, franchise_role, tier_role)
        active_members = []
        for member in team_members:
            if not self.is_subbed_out(member):
                active_members.append(member)
        return active_members

#endregion

#region embed and string format methods

    async def embed_roster(self, ctx: Context, team_name):
        franchise_role, tier_role = await self.get_roles_for_team(ctx.guild, team_name)
        message = await self.format_roster_info(ctx, team_name)

        embed = discord.Embed(description=message, color=tier_role.color)
        emoji = await self.get_franchise_emoji(ctx.guild, franchise_role)
        if(emoji):
            embed.set_thumbnail(url=emoji.url)
        return embed

    async def format_roster_info(self, ctx: Context, team_name: str):
        franchise_role, tier_role = await self.get_roles_for_team(ctx.guild, team_name)
        team_members = self.members_from_team(ctx, franchise_role, tier_role)
        captain = await self._get_team_captain(ctx, franchise_role, tier_role)

        # Sort team_members by player rating if the player ratings cog is used in this server
        try:
            player_ratings: PlayerRatings = self.bot.get_cog("PlayerRatings")
            team_members = await player_ratings.sort_members_by_rating(ctx.guild, team_members)
        except:
            pass

        message = "```\n{0} - {1} - {2}:\n".format(team_name, franchise_role.name, tier_role.name)
        subbed_out_message = ""
        
        for member in team_members:
            role_tags = ["C"] if member == captain else []
            user_message = await self._format_team_member_for_message(ctx, member, *role_tags)
            if self.is_subbed_out(member):
                subbed_out_message += "  {0}\n".format(user_message)
            else:
                message += "  {0}\n".format(user_message)
        if not team_members:
            message += "\nNo members found."
        if not subbed_out_message == "":
            message += "\nSubbed Out:\n{0}".format(subbed_out_message)
        message += "```"
        return message

    async def embed_franchise_captains(self, ctx: Context, franchise_role: discord.Role):
        teams = await self._find_teams_for_franchise(ctx, franchise_role)
        captains_username = []
        team_names = []
        team_tiers = []

        gm = self.get_gm_by_franchise_role(ctx.guild, franchise_role)
        message = "**General Manager:** {0}".format(gm.mention)
        if teams:
            for team in teams:
                f_role, tier_role = await self.get_roles_for_team(ctx.guild, team)
                captain = await self._get_team_captain(ctx, franchise_role, tier_role)
                team_names.append("{0} ({1})".format(team, tier_role.name))
                team_tiers.append(tier_role.name)

                if captain:
                    captains_username.append(str(captain))
                else:
                    captains_username.append("(No captain)")
        else:
            message += "\nNo teams have been made."

        franchise_name = self._extract_franchise_name_from_role(franchise_role)
        embed = discord.Embed(title="{0} Captains:".format(franchise_name), color=discord.Colour.blue(), description=message)
        embed.add_field(name="Team", value="{}\n".format("\n".join(team_names)), inline=True)
        embed.add_field(name="Captain", value="{}\n".format("\n".join(captains_username)), inline=True)
        
        emoji = await self.get_franchise_emoji(ctx.guild, franchise_role)
        if(emoji):
            embed.set_thumbnail(url=emoji.url)
        return embed

    async def embed_tier_captains(self, ctx: Context, tier: str):
        tier_role = self._get_tier_role(ctx, tier)
        teams = await self.get_teams_for_tier(ctx.guild, tier)
        captains = []
        captainless_teams = []
        for team in teams:
            franchise_role, tier_role = await self.get_roles_for_team(ctx.guild, team)
            captain = await self._get_team_captain(ctx, franchise_role, tier_role)
            if captain:
                captains.append((captain, team))
            else:
                gm = self.get_gm_by_franchise_role(ctx.guild, franchise_role)
                captainless_teams.append((gm, team))

        captains.sort(key=lambda captain_team: captain_team[1].casefold())  # dumb.
        captainless_teams.sort(key=lambda gm_team: gm_team[1].casefold())
        
        embed = discord.Embed(title="{0} Captains:".format(tier_role.name), color=tier_role.color)

        captains_formatted = []
        captains_mentioned_formatted = []
        teams_formatted = []
        if captains:
            for captain, team in captains:
                captains_formatted.append(str(captain))
                captains_mentioned_formatted.append(captain.mention)
                teams_formatted.append(team)
                
        if captainless_teams:
            for gm, team in captainless_teams:
                captains_formatted.append("(No captain)")
                teams_formatted.append(team)
        
        embed.add_field(name="Team", value="{}\n".format("\n".join(teams_formatted)), inline=True)
        embed.add_field(name="Captain", value="{}\n".format("\n".join(captains_formatted)), inline=True)
        return embed

#endregion

#region load/save methods

    async def _tiers(self, guild: discord.Guild):
        return await self.config.guild(guild).Tiers()

    async def _save_tiers(self, guild: discord.Guild, tiers):
        await self.config.guild(guild).Tiers.set(tiers)

    async def _teams(self, guild: discord.Guild):
        return await self.config.guild(guild).Teams()

    async def _save_teams(self, guild: discord.Guild, teams):
        await self.config.guild(guild).Teams.set(teams)

    async def _team_roles(self, guild: discord.Guild):
        return await self.config.guild(guild).Team_Roles()

    async def _save_team_roles(self, guild: discord.Guild, team_roles):
        await self.config.guild(guild).Team_Roles.set(team_roles)

#endregion
