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
    async def genericAnnounce(self, ctx, message):
        """Posts the message to the transaction log channel"""
        try:
            _trans_channel = ctx.guild.get_channel(await self._trans_channel(ctx))
            await _trans_channel.send(message)
            await ctx.send("Done")
        except KeyError:
            await ctx.send(":x: Transaction log channel not set")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def draft(self, ctx, user: discord.Member, team_name: str, round: int = None, pick: int = None):
        """Assigns the franchise, tier, and league role to a user when they are drafted and posts to the assigned channel"""
        franchise_role, tier_role = self.team_manager_cog._roles_for_team(ctx, team_name)
        gm_name = self.get_gm_name(franchise_role)
        if franchise_role in user.roles:
            message = "Round {0} Pick {1}: {2} was kept by the {3} ({4} - {5})".format(round, pick, user.mention, team_name, gm_name, tier_role.name)
        else:
            message = "Round {0} Pick {1}: {2} was drafted by the {3} ({4} - {5})".format(round, pick, user.mention, team_name, gm_name, tier_role.name)

        _trans_channel = ctx.guild.get_channel(await self._trans_channel(ctx))
        if _trans_channel is not None:
            try:
                await self.add_player_to_team(ctx, user, team_name)
                freeAgentRole = await self.find_free_agent_role(ctx, user)
                await _trans_channel.send(message)
                draftEligibleRole = None
                for role in user.roles:
                    if role.name == "Draft Eligible":
                        draftEligibleRole = role
                        break
                if freeAgentRole is not None:
                    await user.remove_roles(freeAgentRole)
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
        franchise_role, tier_role = self.team_manager_cog._roles_for_team(ctx, team_name)
        if franchise_role in user.roles and tier_role in user.roles:
            await ctx.send(":x: {0} is already on the {1}".format(user.mention, team_name))
            return

        _trans_channel = ctx.guild.get_channel(await self._trans_channel(ctx))
        if _trans_channel is not None:
           try:
               await self.add_player_to_team(ctx, user, team_name)
               freeAgentRole = await self.find_free_agent_role(ctx, user)
               gm_name = self.get_gm_name(franchise_role)
               message = "{0} was signed by the {1} ({2} - {3})".format(user.mention, team_name, gm_name, tier_role.name)
               await _trans_channel.send(message)
               if freeAgentRole is not None:
                   await user.remove_roles(freeAgentRole)
               await ctx.send("Done")
           except KeyError:
               await ctx.send(":x: Free agent role not found in dictionary")
           except LookupError:
               await ctx.send(":x: Free agent role not found in server")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def cut(self, ctx, user : discord.Member, team_name: str, freeAgentRole: discord.Role = None):
        """Removes the team role and franchise role. Adds the free agent prefix to a user and posts to the assigned channel"""
        franchise_role, tier_role = self.team_manager_cog._roles_for_team(ctx, team_name)
        _trans_channel = ctx.guild.get_channel(await self._trans_channel(ctx))
        if _trans_channel is not None:
            try:
                await self.remove_player_from_team(ctx, user, team_name)
                if freeAgentRole is None:
                    freeAgentRole = self.team_manager_cog._find_role_by_name(ctx, "{0}FA".format(self.team_manager_cog.get_current_tier_role(ctx, user).name))
                await user.edit(nick="FA | {0}".format(self.get_player_nickname(user)))
                await user.add_roles(freeAgentRole)
                gm_name = self.get_gm_name(franchise_role)
                message = "{0} was cut by the {1} ({2} - {3})".format(user.mention, team_name, gm_name, tier_role.name)
                await _trans_channel.send(message)
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
        franchise_role_1, tier_role_1 = self.team_manager_cog._roles_for_team(ctx, new_team_name)
        franchise_role_2, tier_role_2 = self.team_manager_cog._roles_for_team(ctx, new_team_name_2)
        gm_name_1 = self.get_gm_name(franchise_role_1)
        gm_name_2 = self.get_gm_name(franchise_role_2)
        if franchise_role_1 in user.roles and tier_role_1 in user.roles:
            await ctx.send(":x: {0} is already on the {1}".format(user.mention, new_team_name))
            return
        if franchise_role_2 in user_2.roles and tier_role_2 in user_2.roles:
            await ctx.send(":x: {0} is already on the {1}".format(user_2.mention, new_team_name_2))
            return

        _trans_channel = ctx.guild.get_channel(await self._trans_channel(ctx))
        if _trans_channel is not None:
            await self.remove_player_from_team(ctx, user, new_team_name_2)
            await self.remove_player_from_team(ctx, user_2, new_team_name)
            await self.add_player_to_team(ctx, user, new_team_name)
            await self.add_player_to_team(ctx, user_2, new_team_name_2)
            message = "{0} was traded by the {1} ({4} - {5}) to the {2} ({6} - {7}) for {3}".format(user.mention, new_team_name_2, new_team_name, 
                user_2.mention, gm_name_2, tier_role_2.name, gm_name_1, tier_role_1.name)
            await _trans_channel.send(message)
            await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def sub(self, ctx, user: discord.Member, team_name: str):
        """Adds the team role to the user and posts to the assigned channel"""
        _trans_channel = ctx.guild.get_channel(await self._trans_channel(ctx))
        if _trans_channel is not None:
            leagueRole = self.team_manager_cog._find_role_by_name(ctx, "League")
            if leagueRole is not None:
                franchise_role, tier_role = self.team_manager_cog._roles_for_team(ctx, team_name)
                gm_name = self.get_gm_name(franchise_role)
                if franchise_role in user.roles and tier_role in user.roles:
                    await user.remove_roles(franchise_role, tier_role)
                    message = "{0} has finished their time as a substitute for the {1} ({2} - {3})".format(user.name, team_name, gm_name, tier_role.name)
                else:
                    await user.add_roles(franchise_role, tier_role, leagueRole)
                    message = "{0} was signed to a temporary contract by the {1} ({2} - {3})".format(user.mention, team_name, gm_name, tier_role.name)
                await _trans_channel.send(message)
                await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def promote(self, ctx, user: discord.Member, team_name: str):
        old_team_name = await self.team_manager_cog.get_current_team_name(ctx, user)
        if old_team_name is not None:
            if self.team_manager_cog._roles_for_team(ctx, old_team_name)[0] != self.team_manager_cog._roles_for_team(ctx, team_name)[0]:
                await ctx.send(":x: {0} is not in the same franchise as {1}'s current team, the {2}".format(team_name.name, user.name, old_team_name))
                return
            
            _trans_channel = ctx.guild.get_channel(await self._trans_channel(ctx))
            if _trans_channel:
                await self.remove_player_from_team(ctx, user, old_team_name)
                await self.add_player_to_team(ctx, user, team_name)
                franchise_role, tier_role = self.team_manager_cog._roles_for_team(ctx, team_name)
                gm_name = self.get_gm_name(franchise_role)
                message = "{0} was promoted to the {1} ({2} - {3})".format(user.mention, team_name, gm_name, tier_role.name)
                await _trans_channel.send(message)
                await ctx.send("Done")
        else:
            await ctx.send("Either {0} isn't on a team right now or his current team can't be found".format(user.name))

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setTransChannel(self, ctx, trans_channel: discord.Channel):
        await self._save_trans_channel(ctx, trans_channel)

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def getTransChannel(self, ctx):
        try:
            _trans_channel = ctx.guild.get_channel(await self._trans_channel(ctx))
            await ctx.send("Transaction log channel set to: {0}".format(_trans_channel.mention))
        except KeyError:
            await ctx.send(":x: Transaction log channel not set")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def unsetTransChannel(self, ctx):
        await self._save_trans_channel(ctx, None)

    async def add_player_to_team(self, ctx, user, team_name):
        franchise_role, tier_role = self.team_manager_cog._roles_for_team(ctx, team_name)
        # if franchise_role in user.roles and tier_role in user.roles:
        #     await ctx.send(":x: {0} is already on the {1}".format(user.mention, team_name))
        #     return

        leagueRole = self.team_manager_cog._find_role_by_name(ctx, "League")
        if leagueRole is not None:
            prefix = await self.prefix_cog._get_franchise_prefix(ctx, franchise_role)
            if prefix is not None:
                currentTier = self.team_manager_cog.get_current_tier_role(ctx, user)
                if currentTier is not None and currentTier != tier_role:
                    await user.remove_roles(currentTier)
                await user.edit(nick="{0} | {1}".format(prefix, self.get_player_nickname(user)))
                await user.add_roles(tier_role, leagueRole, franchise_role)


    async def remove_player_from_team(self, ctx, user, team_name):
        franchise_role, tier_role = self.team_manager_cog._roles_for_team(ctx, team_name)
        if franchise_role not in user.roles or tier_role not in user.roles:
            await ctx.send(":x: {0} is not on the {1}".format(user.mention, team_name))
            return

        if franchise_role is not None:
            prefix = await self.prefix_cog._get_franchise_prefix(ctx, franchise_role)
            if prefix is not None:
                await user.remove_roles(franchise_role)

    def get_gm_name(self, franchiseRole):
        try:
            return re.findall(r'(?<=\().*(?=\))', franchiseRole.name)[0]
        except:
            raise LookupError('GM name not found from role {0}'.format(franchiseRole.name))

    async def find_free_agent_role(self, ctx, user):
        free_agent_roles = await self.get_free_agent_roles(ctx)
        if(len(free_agent_roles) > 0):
            for fa_role in free_agent_roles:
                for role in user.roles:
                    if role.id == fa_role.id:
                        return role
        return None

    async def get_free_agent_roles(self, ctx):
        free_agent_roles = []
        tiers = await self.team_manager_cog._tiers(ctx)
        for tier in tiers:
            role = self.team_manager_cog._find_role_by_name(ctx, "{0}FA".format(tier))
            if role is not None:
                free_agent_roles.append(role)
        return free_agent_roles

    def get_player_nickname(self, user : discord.Member):
        if user.nick is not None:
            array = user.nick.split(' | ', 1)
            if len(array) == 2:
                currentNickname = array[1].strip()
            else:
                currentNickname = array[0]
            return currentNickname
        return user.name

    async def _trans_channel(self, ctx):
        return await self.config.guild(ctx.guild).TransChannel()

    async def _save_trans_channel(self, ctx, trans_channel):
        await self.config.guild(ctx.guild).TransChannel.set(trans_channel)