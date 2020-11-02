import discord
import re
import ast
import asyncio
import difflib

from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
from collections import Counter
from redbot.core.utils.predicates import MessagePredicate
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions


defaults = {"Tiers": [], "Teams": [], "Team_Roles": {}}
verify_timeout = 30

class TeamManager(commands.Cog):
    """Used to match roles to teams"""

    FRANCHISE_ROLE_KEY = "Franchise Role"
    TIER_ROLE_KEY = "Tier Role"
    GM_ROLE = "General Manager"
    CAPTAN_ROLE = "Captain"
    IR_ROLE = "IR"
    PERM_FA_ROLE = "PermFA"

    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567892, force_registration=True)
        self.config.register_guild(**defaults)
        self.prefix_cog = bot.get_cog("PrefixManager")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def addFranchise(self, ctx, gm: discord.Member, franchise_prefix: str, *, franchise_name: str):
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
            await self._set_user_nickname_prefix(ctx, franchise_prefix, gm)
            await ctx.send("Done.")
        else:
            if self.is_gm(gm):
                await ctx.send("{0} is already a General Manager.".format(gm.name))
            await ctx.send("Franchise was not created.")

    @commands.command()
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def removeFranchise(self, ctx, *, franchise_identifier: str):
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
            await self._set_user_nickname_prefix(ctx, None, gm)
            await ctx.send("Done.")

    @commands.command(aliases=["recoverFranchise", "claimFranchise"])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def transferFranchise(self, ctx, new_gm: discord.Member, *, franchise_identifier: str):
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
        await self._set_user_nickname_prefix(ctx, franchise_prefix, new_gm)

        # reassign roles for gm/franchise
        franchise_tier_roles = await self._find_franchise_tier_roles(ctx, franchise_role)
        gm_role = self._find_role_by_name(ctx, TeamManager.GM_ROLE)
        transfer_roles = [gm_role, franchise_role] + franchise_tier_roles
        await new_gm.add_roles(*transfer_roles)

        # If old GM is still in server:
        old_gm = self._find_member_by_name(ctx, old_gm_name)
        if old_gm:
            await old_gm.remove_roles(*transfer_roles)
            await self._set_user_nickname_prefix(ctx, "", old_gm)
            former_gm_role = self._find_role_by_name(ctx, "Former GM")
            if former_gm_role:
                await old_gm.add_roles(former_gm_role)
            
        
        await ctx.send("{0} is the new General Manager for {1}.".format(new_gm.name, franchise_name))
    
    @commands.command(aliases=["getFranchises", "listFranchises"])
    @commands.guild_only()
    async def franchises(self, ctx):
        """Provides a list of all the franchises set up in the server 
        including the name of the GM for each franchise"""
        franchise_roles = self._get_all_franchise_roles(ctx)
        embed = discord.Embed(title="Franchises:", color=discord.Colour.blue(), 
            description="{}".format("\n".join([role.name for role in franchise_roles])), thumbnail=ctx.guild.icon_url)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.guild_only()
    async def teams(self, ctx, *, franchise_tier_prefix: str):
        """Returns a list of teams based on the input. 
        You can either give it the name of a franchise, a tier, or the prefix for a franchise.
        
        Examples:
        \t[p]teams The Ocean
        \t[p]teams Challenger
        \t[p]teams OCE"""
        # Prefix
        prefixes = await self.prefix_cog._prefixes(ctx)
        if(len(prefixes.items()) > 0):
            for key, value in prefixes.items():
                if franchise_tier_prefix.lower() == value.lower():
                    gm_name = key
                    franchise_role = self._get_franchise_role(ctx, gm_name)
                    await ctx.send(embed=await self._format_teams_for_franchise(ctx, franchise_role))
                    return

        # Tier
        tiers = await self.tiers(ctx)
        for tier in tiers:
            if tier.lower() == franchise_tier_prefix.lower():
                await ctx.send(embed=await self._format_teams_for_tier(ctx, tier))
                return

        # Franchise name
        franchise_role = self.get_franchise_role_from_name(ctx, franchise_tier_prefix)
        if franchise_role is not None:
            await ctx.send(embed=await self._format_teams_for_franchise(ctx, franchise_role))
        else:
            await ctx.send("No franchise, tier, or prefix with name: {0}".format(franchise_tier_prefix))

    @commands.command()
    @commands.guild_only()
    async def roster(self, ctx, *, team_name: str):
        """Shows all the members associated with a team including the GM"""
        team, found = await self._match_team_name(ctx, team_name)
        if found:
            franchise_role, tier_role = await self._roles_for_team(ctx, team)
            if franchise_role is None or tier_role is None:
                await ctx.send("No franchise and tier roles set up for {0}".format(team))
                return
            await ctx.send(embed=await self.create_roster_embed(ctx, team))
        else:
            message = "No team with name: {0}".format(team_name)
            if len(team) > 0:
                message += "\nDo you mean one of these teams:"
                for possible_team in team:
                    message += " `{0}`".format(possible_team)
            await ctx.send(message)

    @commands.command(aliases=["captain", "cptn", "cptns"])
    @commands.guild_only()
    async def captains(self, ctx, *, franchise_tier_prefix: str):
        """Returns a list of team captains under a tier or franchise based on the input. 
        You can either give it the name of a tier, or a franchise identifier (prefix, name, or GM name).
        
        Examples:
        \t[p]captains The Ocean
        \t[p]captains Challenger
        \t[p]captains OCE"""

        found = False
        # Prefix
        prefixes = await self.prefix_cog._prefixes(ctx)
        if(len(prefixes.items()) > 0):
            for key, value in prefixes.items():
                if franchise_tier_prefix.lower() == value.lower() or franchise_tier_prefix.lower() == key.lower():
                    gm_name = key
                    franchise_role = self._get_franchise_role(ctx, gm_name)
                    found = True
        
        # Franchise name
        if not found:
            franchise_role = self.get_franchise_role_from_name(ctx, franchise_tier_prefix)
            if franchise_role is not None:
                found = True
        
        # find captains for franchise by franchise role
        if found:
            await ctx.send(embed=await self._format_franchise_captains(ctx, franchise_role))
            return

        # Tier
        tiers = await self.tiers(ctx)
        for tier in tiers:
            if tier.lower() == franchise_tier_prefix.lower():
                found = True
                await ctx.send(embed=await self._format_tier_captains(ctx, tier))
                return
        
        await ctx.send("No franchise, tier, or prefix with name: {0}".format(franchise_tier_prefix))

    @commands.command(aliases=["tiers", "getTiers"])
    @commands.guild_only()
    async def listTiers(self, ctx):
        """Provides a list of all the tiers set up in the server"""
        tiers = await self.tiers(ctx)
        if tiers:
            await ctx.send(
                "Tiers set up in this server: {0}".format(", ".join(tiers)))
        else:
            await ctx.send("No tiers set up in this server.")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def addTier(self, ctx, tier_name: str):
        """Add a tier to the tier list and creates corresponding roles. 
        This will need to be done before any transactions can be done for players in this tier"""
        await self._create_role(ctx, tier_name)
        await self._create_role(ctx, "{0}FA".format(tier_name))
        tiers = await self.tiers(ctx)
        tiers.append(tier_name)
        await self._save_tiers(ctx, tiers)
        await ctx.send("Done.")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def removeTier(self, ctx, tier_name: str):
        """Remove a tier from the tier list and the tier's corresponding roles"""

        if len(await self._find_teams_for_tier(ctx, tier_name)) > 0:
            await ctx.send(":x: Cannot remove a tier that has teams enrolled.")
        else:
            tier_role = self._get_tier_role(ctx, tier_name)
            tier_fa_role = self._find_role_by_name(ctx, "{0}FA".format(tier_name))
            if tier_role:
                await tier_role.delete()
            if tier_fa_role:
                await tier_fa_role.delete()
            tiers = await self.tiers(ctx)
            try:
                tiers.remove(tier_name)
            except ValueError:
                await ctx.send(
                    "{0} does not seem to be a tier.".format(tier_name))
                return
            await self._save_tiers(ctx, tiers)
            await ctx.send("Done.")

    @commands.command(aliases=["getTeams"])
    @commands.guild_only()
    async def listTeams(self, ctx):
        """Provides a list of all the teams set up in the server"""
        teams = await self._teams(ctx)
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
    async def teamRoles(self, ctx, team_name: str):
        """Prints out the franchise and tier role that corresponds with the given team"""
        franchise_role, tier_role = await self._roles_for_team(ctx, team_name)
        if franchise_role and tier_role:
            await ctx.send(
                    "Franchise role for {0} = {1}\nTier role for {0} = {2}".format(team_name, franchise_role.name, tier_role.name))
        else:
            await ctx.send("No franchise and tier roles set up for {0}".format(team_name))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def addTeams(self, ctx, *teams_to_add):
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
                await ctx.send("Adding team: {0}".format(repr(team)))
                teamAdded = await self._add_team(ctx, *team)
                if teamAdded:
                    addedCount += 1
        finally:
            await ctx.send("Added {0} team(s).".format(addedCount))
        await ctx.send("Done.")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def addTeam(self, ctx, team_name: str, gm_name: str, tier: str):
        """Add a single team and it's corresponding roles to the file system to be used for transactions and match info"""
        teamAdded = await self._add_team(ctx, team_name, gm_name, tier)
        if(teamAdded):
            await ctx.send("Done.")
        else:
            await ctx.send("Error adding team: {0}".format(team_name))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def removeTeam(self, ctx, *, team_name: str):
        """Removes team from the file system. Team roles will be cleared as well"""
        teamRemoved = await self._remove_team(ctx, team_name)
        if teamRemoved:
            await ctx.send("Done.")
        else:
            await ctx.send("Error removing team: {0}".format(team_name))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearTeams(self, ctx):
        """Removes all teams from the file system. Team roles will be cleared as well"""
        teams = await self._teams(ctx)
        team_roles = await self._team_roles(ctx)

        teams.clear()
        team_roles.clear()
        
        await self._save_teams(ctx, teams)
        await self._save_team_roles(ctx, team_roles)
        await ctx.send("Done.")

    @commands.command(aliases=["fa", "fas"])
    @commands.guild_only()
    async def freeAgents(self, ctx, tier: str, filter=None):
        """
        Gets a list of all free agents in a specific tier
         - Filters for PermFA: perm, permfa, restricted, p, r, rfa, permanent
         - Filters for signable FAs: non-perm, unrestricted, u, ufa, signable
        """
        tiers = await self.tiers(ctx)
        tier_name = None
        for _tier in tiers:
            if tier.lower() == _tier.lower():
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
                    if filter.lower() in perm_fa_filters:
                        if perm_fa_role is not None and perm_fa_role in member.roles:
                            message += "\n{0} {1}".format(member.display_name, ("(Permanent FA)"))
                    elif filter.lower() in signable_fa_filters:
                        if perm_fa_role is not None and perm_fa_role not in member.roles:
                            message += "\n{0}".format(member.display_name)
                else:
                    message += "\n{0}".format(member.display_name)
                    if perm_fa_role is not None and perm_fa_role in member.roles:
                        message += " (Permanent FA)"
        message += "```"

        color = discord.Colour.blue()
        for role in ctx.guild.roles:
            if role.name.lower() == tier_name.lower():
                color = role.color
        embed = discord.Embed(title="{0} Free Agents:".format(tier_name), color=color, 
            description=message, thumbnail=ctx.guild.icon_url)
                    
        await ctx.send(embed=embed)


    async def _react_prompt(self, ctx, prompt, if_not_msg=None):
        user = ctx.message.author
        react_msg = await ctx.send(prompt)
        start_adding_reactions(react_msg, ReactionPredicate.YES_OR_NO_EMOJIS)
        try:
            pred = ReactionPredicate.yes_or_no(react_msg, user)
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=verify_timeout)
            if pred.result:
                return True
            if if_not_msg:
                await ctx.send(if_not_msg)
            return False
        except asyncio.TimeoutError:
            await ctx.send("Sorry {}, you didn't react quick enough. Please try again.".format(user.mention))
            return False

    async def _get_franchise_data(self, ctx, franchise_identifier):
        franchise_found = False
        # GM/Prefix Identifier
        prefixes = await self.prefix_cog._prefixes(ctx)
        if(len(prefixes.items()) > 0):
            for key, value in prefixes.items():
                if franchise_identifier.lower() == key.lower() or franchise_identifier.lower() == value.lower():
                    franchise_found = True
                    gm_name = key
                    franchise_prefix = value
                    franchise_role = self._get_franchise_role(ctx, gm_name)
                    franchise_name = self.get_franchise_name_from_role(franchise_role)
                    
                
        # Franchise name identifier
        if not franchise_found:
            franchise_role = self.get_franchise_role_from_name(ctx, franchise_identifier)
            if franchise_role:
                franchise_found = True
                franchise_name = self.get_franchise_name_from_role(franchise_role)
                gm_name = self._get_gm_name(franchise_role)
                franchise_prefix = await self.prefix_cog._get_gm_prefix(ctx, gm_name)

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

    async def teams_for_user(self, ctx, user):
        tiers = await self.tiers(ctx)
        teams = []
        franchise_role = self.get_current_franchise_role(user)
        for role in user.roles:
            if role.name in tiers:
                tier_role = role
                team_name = await self._find_team_name(ctx, franchise_role, tier_role)
                teams.append(team_name)
        return teams

    def gm_and_members_from_team(self, ctx, franchise_role, tier_role):
        """Retrieve tuple with the gm user and a list of other users that are
        on the team indicated by the provided franchise_role and tier_role.
        """
        gm = None
        team_members = []
        for member in ctx.message.guild.members:
            if franchise_role in member.roles:
                if self.is_gm(member):
                    gm = member
                elif tier_role in member.roles:
                    team_members.append(member)
        return (gm, team_members)

    async def create_roster_embed(self, ctx, team_name):
        franchise_role, tier_role = await self._roles_for_team(ctx, team_name)
        message = await self.format_roster_info(ctx, team_name)

        embed = discord.Embed(description=message, color=tier_role.color)
        emoji = await self._get_franchise_emoji(ctx, franchise_role)
        if(emoji):
            embed.set_thumbnail(url=emoji.url)
        return embed

    async def format_roster_info(self, ctx, team_name: str):
        franchise_role, tier_role = await self._roles_for_team(ctx, team_name)
        gm, team_members = self.gm_and_members_from_team(ctx, franchise_role, tier_role)
        captain = await self._get_team_captain(ctx, franchise_role, tier_role)

        message = "```\n{0} ({1}):\n".format(team_name, tier_role.name)
        if gm:
            if gm == captain:
                message += "  {0}\n".format(
                    self._format_team_member_for_message(gm, "C"))
            else:
                message += "  {0}\n".format(
                    self._format_team_member_for_message(gm))
        for member in team_members:
            role_tags = ["C"] if member == captain else []
            message += "  {0}\n".format(
                self._format_team_member_for_message(member, *role_tags))
        if not team_members:
            message += "\nNo other members found."
        message += "```"
        return message

    async def _format_franchise_captains(self, ctx, franchise_role: discord.Role):
        teams = await self._find_teams_for_franchise(ctx, franchise_role)
        captains_mentioned = []
        captains_username = []
        team_names = []
        team_tiers = []

        gm = self._get_gm(ctx, franchise_role)
        message = "**General Manager:** {0}".format(gm.mention)
        if teams:
            for team in teams:
                f_role, tier_role = await self._roles_for_team(ctx, team)
                captain = await self._get_team_captain(ctx, franchise_role, tier_role)
                team_names.append("{0} ({1})".format(team, tier_role.name))
                team_tiers.append(tier_role.name)

                if captain:
                    # captains_mentioned.append(captain.mention) # mention disabled
                    captains_username.append(str(captain))
                else:
                    # captains_mentioned.append("(No captain)")
                    captains_username.append("(No captain)")  #.append("N/A") # mention disabled
        else:
            message += "\nNo teams have been made."

        franchise_name = self._extract_franchise_name_from_role(franchise_role)
        embed = discord.Embed(title="{0} Captains:".format(franchise_name), color=discord.Colour.blue(), description=message)
        embed.add_field(name="Team", value="{}\n".format("\n".join(team_names)), inline=True)
        # embed.add_field(name="Tier", value="{}\n".format("\n".join(team_tiers)), inline=True)
        # embed.add_field(name="Captain", value="{}\n".format("\n".join(captains_mentioned)), inline=True)  # name = Captain
        embed.add_field(name="Captain", value="{}\n".format("\n".join(captains_username)), inline=True)     # name = Username
        
        emoji = await self._get_franchise_emoji(ctx, franchise_role)
        if(emoji):
            embed.set_thumbnail(url=emoji.url)
        return embed

    async def _format_tier_captains(self, ctx, tier: str):
        tier_role = self._get_tier_role(ctx, tier)
        teams = await self._find_teams_for_tier(ctx, tier)
        captains = []
        captainless_teams = []
        for team in teams:
            franchise_role, tier_role = await self._roles_for_team(ctx, team)
            captain = await self._get_team_captain(ctx, franchise_role, tier_role)
            if captain:
                captains.append((captain, team))
            else:
                gm = self._get_gm(ctx, franchise_role)
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
                captains_formatted.append("(No captain)")  #.append("N/A")
                # captains_mentioned_formatted.append("(No Captain)")
                teams_formatted.append(team)
        
        embed.add_field(name="Team", value="{}\n".format("\n".join(teams_formatted)), inline=True)
        # embed.add_field(name="Captain", value="{}\n".format("\n".join(captains_mentioned_formatted)), inline=True)    # mention disabled
        embed.add_field(name="Captain", value="{}\n".format("\n".join(captains_formatted)), inline=True)                # name="Username"
        return embed

    async def _get_team_captain(self, ctx, franchise_role: discord.Role, tier_role: discord.Role):
        captain_role = self._find_role_by_name(ctx, "Captain")
        gm, members = self.gm_and_members_from_team(ctx, franchise_role, tier_role)
        for member in members:
            if captain_role in member.roles:
                return member
        if gm and captain_role in gm.roles:
            return gm
        return None
            
    async def _create_role(self, ctx, role_name: str):
        """Creates and returns a new Guild Role"""
        for role in ctx.guild.roles:
            if role.name == role_name:
                await ctx.send("The role \"{0}\" already exists in the server.".format(role_name))
                return None
        return await ctx.guild.create_role(name=role_name)

    def _format_team_member_for_message(self, member, *args):
        extraRoles = list(args)
        if self.is_gm(member):
            extraRoles.insert(0, "GM")
        if self.is_IR(member):
            extraRoles.append("IR")
        roleString = ""
        if extraRoles:
            roleString = " ({0})".format("|".join(extraRoles))
        return "{0}{1}".format(member.display_name, roleString)

    async def _format_teams_for_franchise(self, ctx, franchise_role):
        teams = await self._find_teams_for_franchise(ctx, franchise_role)
        teams_message = ""
        for team in teams:
            tier_role = (await self._roles_for_team(ctx, team))[1]
            teams_message += "\n\t{0} ({1})".format(team, tier_role.name)

        embed = discord.Embed(title="{0}:".format(franchise_role.name), color=discord.Colour.blue(), description=teams_message)
        emoji = await self._get_franchise_emoji(ctx, franchise_role)
        if(emoji):
            embed.set_thumbnail(url=emoji.url)
        return embed

    async def _format_teams_for_tier(self, ctx, tier):
        teams = await self._find_teams_for_tier(ctx, tier)
        teams_message = ""
        for team in teams:
            franchise_role = (await self._roles_for_team(ctx, team))[0]
            gmNameFromRole = re.findall(r'(?<=\().*(?=\))', franchise_role.name)[0]
            teams_message += "\n\t{0} ({1})".format(team, gmNameFromRole)

        color = discord.Colour.blue()
        for role in ctx.guild.roles:
            if role.name.lower() == tier.lower():
                color = role.color

        embed = discord.Embed(title="{0} teams:".format(tier), color=color, description=teams_message)
        return embed

    async def tiers(self, ctx):
        return await self.config.guild(ctx.guild).Tiers()

    async def _save_tiers(self, ctx, tiers):
        await self.config.guild(ctx.guild).Tiers.set(tiers)

    def _extract_tier_from_role(self, team_role):
        tier_matches = re.findall(r'\w*\b(?=\))', team_role.name)
        return None if not tier_matches else tier_matches[0]

    def _extract_franchise_name_from_role(self, franchise_role: discord.Role):
        franchise_name_gm = franchise_role.name
        franchise_name = franchise_name_gm[:franchise_name_gm.index(" (")]
        return franchise_name
    
    async def _add_team(self, ctx, team_name: str, gm_name: str, tier: str):
        teams = await self._teams(ctx)
        team_roles = await self._team_roles(ctx)

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
        await self._save_teams(ctx, teams)
        await self._save_team_roles(ctx, team_roles)
        gm = self._get_gm(ctx, franchise_role)
        await gm.add_roles(tier_role)
        return True
    
    async def _remove_team(self, ctx, team_name: str):
        franchise_role, tier_role = await self._roles_for_team(ctx, team_name)
        teams = await self._teams(ctx)
        team_roles = await self._team_roles(ctx)
        try:
            teams.remove(team_name)
            del team_roles[team_name]
        except ValueError:
            await ctx.send("{0} does not seem to be a team.".format(team_name))
            return False
        await self._save_teams(ctx, teams)
        await self._save_team_roles(ctx, team_roles)
        gm = self._get_gm(ctx, franchise_role)
        await gm.remove_roles(tier_role)
        return True

    def _get_tier_role(self, ctx, tier: str):
        roles = ctx.message.guild.roles
        for role in roles:
            if role.name.lower() == tier.lower():
                return role
        return None

    async def _teams(self, ctx):
        return await self.config.guild(ctx.guild).Teams()

    async def _save_teams(self, ctx, teams):
        await self.config.guild(ctx.guild).Teams.set(teams)

    async def _team_roles(self, ctx):
        return await self.config.guild(ctx.guild).Team_Roles()

    async def _save_team_roles(self, ctx, team_roles):
        await self.config.guild(ctx.guild).Team_Roles.set(team_roles)

    def _find_role(self, ctx, role_id):
        for role in ctx.message.guild.roles:
            if role.id == role_id:
                return role
        raise LookupError('No role with id: {0} found in server roles'.format(role_id))

    def _find_role_by_name(self, ctx, role_name):
        for role in ctx.message.guild.roles:
            if role.name.lower() == role_name.lower():
                return role
        return None

    def _find_member_by_name(self, ctx, member_name: str):
        for member in ctx.guild.members:
            if member.name == member_name:
                return member
        return None
    
    def _get_franchise_role(self, ctx, gm_name):
        for role in ctx.message.guild.roles:
            try:
                gmNameFromRole = re.findall(r'(?<=\().*(?=\))', role.name)[0]
                if gmNameFromRole == gm_name:
                    return role
            except:
                continue

    def _get_all_franchise_roles(self, ctx):
        franchise_roles = []
        for role in ctx.message.guild.roles:
            try:
                gmNameFromRole = re.findall(r'(?<=\().*(?=\))', role.name)[0]
                if gmNameFromRole is not None:
                    franchise_roles.append(role)
            except:
                continue
        return franchise_roles

    async def _roles_for_team(self, ctx, team_name: str):
        teams = await self._teams(ctx)
        if teams and team_name in teams:
            team_roles = await self._team_roles(ctx)
            team_data = team_roles.setdefault(team_name, {})
            franchise_role_id = team_data["Franchise Role"]
            tier_role_id = team_data["Tier Role"]
            franchise_role = self._find_role(ctx, franchise_role_id)
            tier_role = self._find_role(ctx, tier_role_id)
            return (franchise_role, tier_role)
        else:
           raise LookupError('No team with name: {0}'.format(team_name))

    async def _find_team_name(self, ctx, franchise_role, tier_role):
        teams = await self._teams(ctx)
        for team in teams:
            if await self._roles_for_team(ctx, team) == (franchise_role, tier_role):
                return team

    async def _find_teams_for_franchise(self, ctx, franchise_role):
        franchise_teams = []
        teams = await self._teams(ctx)
        for team in teams:
            if (await self._roles_for_team(ctx, team))[0] == franchise_role:
                franchise_teams.append(team)
        return franchise_teams

    async def _find_franchise_tier_roles(self, ctx, franchise_role: discord.Role):
        franchise_tier_roles = []
        teams = await self._teams(ctx)
        for team in teams:
            if (await self._roles_for_team(ctx, team))[0] == franchise_role:
                tier_role = (await self._roles_for_team(ctx, team))[1]
                franchise_tier_roles.append(tier_role)
        return franchise_tier_roles

    async def _get_franchise_tier_team(self, ctx, franchise_role: discord.Role, tier_role: discord.Role):
        teams = await self._teams(ctx)
        for team in teams:
            if (await self._roles_for_team(ctx, team)) == (franchise_role, tier_role):
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

    async def get_current_tier_role(self, ctx, user: discord.Member):
        tierList = await self.tiers(ctx)
        for role in user.roles:
            if role.name in tierList:
                return role
        return None

    async def get_current_team_name(self, ctx, user: discord.Member):
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

    async def _set_user_nickname_prefix(self, ctx, prefix: str, user: discord.member):
        try:
            if prefix:
                await user.edit(nick="{0} | {1}".format(prefix, self.get_player_nickname(user)))
            else:
                await user.edit(nick=self.get_player_nickname(user))
        except discord.Forbidden:
            await ctx.send("Changing nickname forbidden for user: {0}".format(user.name))

    def get_franchise_role_from_name(self, ctx, franchise_name: str):
        for role in ctx.message.guild.roles:
            try:
                matchedString = re.findall(r'.+?(?= \()', role.name)[0]
                if matchedString.lower() == franchise_name.lower():
                    return role
            except:
                continue

    def get_franchise_name_from_role(self, franchise_role: discord.Role):
        end_of_name = franchise_role.name.rindex("(") - 1
        return franchise_role.name[0:end_of_name]

    async def _match_team_name(self, ctx, team_name):
        teams = await self._teams(ctx)
        for team in teams:
            if team_name.lower() == team.lower():
                return team, True
        return difflib.get_close_matches(team_name, teams, n=3, cutoff=0.4), False

    async def _match_tier_name(self, ctx, tier_name):
        tiers = await self.tiers(ctx)
        for tier in tiers:
            if tier_name.lower() == tier.lower():
                return tier
        close_match = difflib.get_close_matches(tier_name, tiers, n=1, cutoff=0.6)
        if len(close_match) > 0:
            return close_match[0]
        return None

    async def _find_teams_for_tier(self, ctx, tier):
        teams_in_tier = []
        teams = await self._teams(ctx)
        for team in teams:
            team_tier = (await self._roles_for_team(ctx, team))[1]
            if team_tier.name.lower() == tier.lower():
                teams_in_tier.append(team)
        return teams_in_tier

    async def _get_franchise_emoji(self, ctx, franchise_role):
        prefix = await self.prefix_cog._get_franchise_prefix(ctx, franchise_role)
        gm_name = self._get_gm_name(franchise_role)
        if prefix:
            emojis = ctx.guild.emojis
            for emoji in emojis:
                if emoji.name.lower() == prefix.lower() or emoji.name.lower() == gm_name.lower():
                    return emoji

    def _get_gm(self, ctx, franchise_role):
        for member in ctx.message.guild.members:
            if franchise_role in member.roles:
                if self.is_gm(member):
                    return member
        
    def _get_gm_name(self, franchise_role):
        try:
            return re.findall(r'(?<=\().*(?=\))', franchise_role.name)[0]
        except:
            raise LookupError('GM name not found from role {0}'.format(franchise_role.name))
    
    async def _get_user_tier_roles(self, ctx, user: discord.Member):
        user_tier_roles = []
        for tier_name in await self._tiers(ctx):
            tier_role = self._find_role_by_name(ctx, tier_name)
            if tier_role in user.roles:
                user_tier_roles.append(tier_role)
        return user_tier_roles
    
    
