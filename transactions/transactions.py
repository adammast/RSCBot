import discord
import re

from redbot.core import Config
from redbot.core import commands
from redbot.core import checks

defaults = {"TransChannel": None}

class Transactions(commands.Cog):
    """Used to set franchise and role prefixes and give to members in those franchises or with those roles"""

    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567895, force_registration=True)
        self.config.register_guild(**defaults)
        self.team_manager_cog = bot.get_cog("TeamManager")
        self.prefix_cog = bot.get_cog("PrefixManager")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def genericAnnounce(self, ctx, *, message):
        """Posts the message to the transaction log channel"""
        try:
            trans_channel = await self._trans_channel(ctx)
            await trans_channel.send(message)
            await ctx.send("Done")
        except KeyError:
            await ctx.send(":x: Transaction log channel not set")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def draft(self, ctx, user: discord.Member, team_name: str, round: int = None, pick: int = None):
        """Assigns the franchise, tier, and league role to a user when they are drafted and posts to the assigned channel"""
        franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, team_name)
        gm_name = self._get_gm_name(ctx, franchise_role)
        if franchise_role in user.roles:
            message = "Round {0} Pick {1}: {2} was kept by the {3} ({4} - {5})".format(round, pick, user.mention, team_name, gm_name, tier_role.name)
        else:
            message = "Round {0} Pick {1}: {2} was drafted by the {3} ({4} - {5})".format(round, pick, user.mention, team_name, gm_name, tier_role.name)

        trans_channel = await self._trans_channel(ctx)
        if trans_channel is not None:
            try:
                await self.add_player_to_team(ctx, user, team_name)
                free_agent_roles = await self.find_user_free_agent_roles(ctx, user)
                await trans_channel.send(message)
                draftEligibleRole = None
                for role in user.roles:
                    if role.name == "Draft Eligible":
                        draftEligibleRole = role
                        break
                if len(free_agent_roles) > 0:
                   for role in free_agent_roles:
                       await user.remove_roles(role)
                if draftEligibleRole is not None:
                    await user.remove_roles(draftEligibleRole)
                await ctx.send("Done")
            except KeyError:
                await ctx.send(":x: Free agent role not found in dictionary")
            except LookupError:
                await ctx.send(":x: Free agent role not found in server")
            return

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def sign(self, ctx, user: discord.Member, team_name: str):
        """Assigns the team role, franchise role and prefix to a user when they are signed and posts to the assigned channel"""
        franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, team_name)
        if franchise_role in user.roles and tier_role in user.roles:
            await ctx.send(":x: {0} is already on the {1}".format(user.mention, team_name))
            return

        trans_channel = await self._trans_channel(ctx)
        if trans_channel is not None:
           try:
               await self.add_player_to_team(ctx, user, team_name)
               free_agent_roles = await self.find_user_free_agent_roles(ctx, user)
               if len(free_agent_roles) > 0:
                   for role in free_agent_roles:
                       await user.remove_roles(role)
               gm_name = self._get_gm_name(ctx, franchise_role)
               message = "{0} was signed by the {1} ({2} - {3})".format(user.mention, team_name, gm_name, tier_role.name)
               await trans_channel.send(message)
               await ctx.send("Done")
           except Exception as e:
               await ctx.send(e)

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def cut(self, ctx, user : discord.Member, team_name: str, tier_fa_role: discord.Role = None):
        """Removes the team role and franchise role. Adds the free agent prefix and role to a user and posts to the assigned channel"""
        franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, team_name)
        trans_channel = await self._trans_channel(ctx)
        if trans_channel is not None:
            try:
                await self.remove_player_from_team(ctx, user, team_name)
                if tier_fa_role is None:
                    role_name = "{0}FA".format((await self.team_manager_cog.get_current_tier_role(ctx, user)).name)
                    tier_fa_role = self.team_manager_cog._find_role_by_name(ctx, role_name)
                fa_role = self.team_manager_cog._find_role_by_name(ctx, "Free Agent")
                await self.team_manager_cog._set_user_nickname_prefix(ctx, "FA", user)
                await user.add_roles(tier_fa_role, fa_role)
                gm_name = self._get_gm_name(ctx, franchise_role)
                message = "{0} was cut by the {1} ({2} - {3})".format(user.mention, team_name, gm_name, tier_role.name)
                await trans_channel.send(message)
                await ctx.send("Done")
            except KeyError:
                await ctx.send(":x: Free agent role not found in dictionary")
            except LookupError:
                await ctx.send(":x: Free agent role not found in server")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def trade(self, ctx, user: discord.Member, new_team_name: str, user_2: discord.Member, new_team_name_2: str):
        """Swaps the teams of the two players and announces the trade in the assigned channel"""
        franchise_role_1, tier_role_1 = await self.team_manager_cog._roles_for_team(ctx, new_team_name)
        franchise_role_2, tier_role_2 = await self.team_manager_cog._roles_for_team(ctx, new_team_name_2)
        gm_name_1 = self._get_gm_name(ctx, franchise_role_1)
        gm_name_2 = self._get_gm_name(ctx, franchise_role_2)
        if franchise_role_1 in user.roles and tier_role_1 in user.roles:
            await ctx.send(":x: {0} is already on the {1}".format(user.mention, new_team_name))
            return
        if franchise_role_2 in user_2.roles and tier_role_2 in user_2.roles:
            await ctx.send(":x: {0} is already on the {1}".format(user_2.mention, new_team_name_2))
            return

        trans_channel = await self._trans_channel(ctx)
        if trans_channel is not None:
            await self.remove_player_from_team(ctx, user, new_team_name_2)
            await self.remove_player_from_team(ctx, user_2, new_team_name)
            await self.add_player_to_team(ctx, user, new_team_name)
            await self.add_player_to_team(ctx, user_2, new_team_name_2)
            message = "{0} was traded by the {1} ({4} - {5}) to the {2} ({6} - {7}) for {3}".format(user.mention, new_team_name_2, new_team_name, 
                user_2.mention, gm_name_2, tier_role_2.name, gm_name_1, tier_role_1.name)
            await trans_channel.send(message)
            await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def sub(self, ctx, user: discord.Member, team_name: str):
        """
        Adds the team roles to the user and posts to the assigned transaction channel
        
        This command is also used to end substitution periods"""
        trans_channel = await self._trans_channel(ctx)
        free_agent_role = self.team_manager_cog._find_role_by_name(ctx, "Free Agent")
        if trans_channel is not None:
            leagueRole = self.team_manager_cog._find_role_by_name(ctx, "League")
            if leagueRole is not None:
                franchise_role, team_tier_role = await self.team_manager_cog._roles_for_team(ctx, team_name)
                
                # End Substitution
                if franchise_role in user.roles and team_tier_role in user.roles:
                    if free_agent_role in user.roles:
                        await user.remove_roles(franchise_role)
                        fa_tier_role = self.team_manager_cog._find_role_by_name(ctx, "{0}FA".format(team_tier_role))
                        if not fa_tier_role in user.roles:
                            player_tier = await self.get_tier_role_for_fa(ctx, user)
                            await user.remove_roles(team_tier_role)
                            await user.add_roles(player_tier)
                    else:
                        await user.remove_roles(team_tier_role)
                    gm = self._get_gm_name(ctx, franchise_role, True)
                    message = "{0} has finished their time as a substitute for the {1} ({2} - {3})".format(user.name, team_name, gm, team_tier_role.name)
                
                # Begin Substitution:
                else:
                    if free_agent_role in user.roles:
                        player_tier = await self.get_tier_role_for_fa(ctx, user)
                        await user.remove_roles(player_tier)
                    await user.add_roles(franchise_role, team_tier_role, leagueRole)
                    gm = self._get_gm_name(ctx, franchise_role)
                    message = "{0} was signed to a temporary contract by the {1} ({2} - {3})".format(user.mention, team_name, gm, team_tier_role.name)
                await trans_channel.send(message)
                await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def promote(self, ctx, user: discord.Member, team_name: str):
        """Adds the team tier role to the user and posts to the assigned channel"""
        old_team_name = await self.team_manager_cog.get_current_team_name(ctx, user)
        if old_team_name is not None:
            if (await self.team_manager_cog._roles_for_team(ctx, old_team_name))[0] != (await self.team_manager_cog._roles_for_team(ctx, team_name))[0]:
                await ctx.send(":x: {0} is not in the same franchise as {1}'s current team, the {2}".format(team_name.name, user.name, old_team_name))
                return
            
            trans_channel = await self._trans_channel(ctx)
            if trans_channel:
                await self.remove_player_from_team(ctx, user, old_team_name)
                await self.add_player_to_team(ctx, user, team_name)
                franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, team_name)
                gm_name = self._get_gm_name(ctx, franchise_role)
                message = "{0} was promoted to the {1} ({2} - {3})".format(user.mention, team_name, gm_name, tier_role.name)
                await trans_channel.send(message)
                await ctx.send("Done")
        else:
            await ctx.send("Either {0} isn't on a team right now or his current team can't be found".format(user.name))

    @commands.guild_only()
    @commands.command(aliases=["setTransChannel"])
    @checks.admin_or_permissions(manage_guild=True)
    async def setTransactionChannel(self, ctx, trans_channel: discord.TextChannel):
        """Sets the channel where all transaction messages will be posted"""
        await self._save_trans_channel(ctx, trans_channel.id)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command(aliases=["getTransChannel"])
    @checks.admin_or_permissions(manage_guild=True)
    async def getTransactionChannel(self, ctx):
        """Gets the channel currently assigned as the transaction channel"""
        try:
            await ctx.send("Transaction log channel set to: {0}".format((await self._trans_channel(ctx)).mention))
        except:
            await ctx.send(":x: Transaction log channel not set")

    @commands.guild_only()
    @commands.command(aliases=["unsetTransChannel"])
    @checks.admin_or_permissions(manage_guild=True)
    async def unsetTransactionChannel(self, ctx):
        """Unsets the transaction channel. Transactions will not be performed if no transaction channel is set"""
        await self._save_trans_channel(ctx, None)
        await ctx.send("Done")


    async def add_player_to_team(self, ctx, user, team_name):
        franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, team_name)
        # if franchise_role in user.roles and tier_role in user.roles:
        #     await ctx.send(":x: {0} is already on the {1}".format(user.mention, team_name))
        #     return

        leagueRole = self.team_manager_cog._find_role_by_name(ctx, "League")
        if leagueRole is not None:
            prefix = await self.prefix_cog._get_franchise_prefix(ctx, franchise_role)
            if prefix is not None:
                currentTier = await self.team_manager_cog.get_current_tier_role(ctx, user)
                if currentTier is not None and currentTier != tier_role:
                    await user.remove_roles(currentTier)
                await self.team_manager_cog._set_user_nickname_prefix(ctx, prefix, user)
                await user.add_roles(tier_role, leagueRole, franchise_role)

    async def remove_player_from_team(self, ctx, user, team_name):
        franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, team_name)
        if franchise_role not in user.roles or tier_role not in user.roles:
            await ctx.send(":x: {0} is not on the {1}".format(user.mention, team_name))
            return

        if franchise_role is not None:
            prefix = await self.prefix_cog._get_franchise_prefix(ctx, franchise_role)
            if prefix is not None:
                await user.remove_roles(franchise_role)

    async def find_user_free_agent_roles(self, ctx, user):
        free_agent_roles = await self.get_free_agent_roles(ctx)
        user_fa_roles = []
        if(len(free_agent_roles) > 0):
            for fa_role in free_agent_roles:
                for role in user.roles:
                    if role.id == fa_role.id:
                        user_fa_roles.append(role)
        return user_fa_roles

    async def get_free_agent_roles(self, ctx):
        free_agent_roles = []
        tiers = await self.team_manager_cog.tiers(ctx)
        for tier in tiers:
            role = self.team_manager_cog._find_role_by_name(ctx, "{0}FA".format(tier))
            if role is not None:
                free_agent_roles.append(role)
        free_agent_roles.append(self.team_manager_cog._find_role_by_name(ctx, "Free Agent"))
        return free_agent_roles

    def get_player_nickname(self, user : discord.Member):
        return self.team_manager_cog.get_player_nickname(user)
    
    async def set_user_nickname_prefix(self, ctx, prefix: str, user: discord.member):
        return self.team_manager_cog._set_user_nickname_prefix(ctx, prefix, user)

    async def get_tier_role_for_fa(self, ctx, user : discord.Member):
        fa_roles = await self.find_user_free_agent_roles(ctx, user)
        standard_fa_role = self.team_manager_cog._find_role_by_name(ctx, "Free Agent")
        if standard_fa_role in fa_roles:
            fa_roles.remove(standard_fa_role)
        tier_role_name = fa_roles[0].name[:-2]
        tier_role = self.team_manager_cog._find_role_by_name(ctx, tier_role_name)
        return tier_role

    def _get_gm_name(self, ctx, franchise_role, returnNameAsString=False):
        gm = self.team_manager_cog._get_gm(ctx, franchise_role)
        if gm:
            if returnNameAsString:
                return gm.name
            else:
                return gm.mention
        else:
           return self.team_manager_cog._get_gm_name(franchise_role)

    async def _trans_channel(self, ctx):
        return ctx.guild.get_channel(await self.config.guild(ctx.guild).TransChannel())

    async def _save_trans_channel(self, ctx, trans_channel):
        await self.config.guild(ctx.guild).TransChannel.set(trans_channel)
