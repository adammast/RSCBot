import discord
from discord.ext.commands import Context
from playerRatings import PlayerRatings
from prefixManager import PrefixManager
from redbot.core import Config, checks, commands
from teamManager import TeamManager

defaults = {
    "TransChannel": None,
    "DevLeagueTiers": [],
    "DevLeagueCutMessage": None,
    "NoDevLeagueCutMessage": None
}

class Transactions(commands.Cog):
    """Used to set franchise and role prefixes and give to members in those franchises or with those roles"""

    SUBBED_OUT_ROLE = "Subbed Out"

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567895, force_registration=True)
        self.config.register_guild(**defaults)
        self.prefix_cog: PrefixManager = bot.get_cog("PrefixManager")
        self.team_manager_cog: TeamManager = bot.get_cog("TeamManager")

#region commmands

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def genericAnnounce(self, ctx: Context, *, message):
        """Posts the message to the transaction log channel"""
        try:
            trans_channel = await self._trans_channel(ctx.guild)
            await trans_channel.send(message)
            await ctx.send("Done")
        except KeyError:
            await ctx.send(":x: Transaction log channel not set")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def draft(self, ctx: Context, user: discord.Member, team_name: str, round: int = None, pick: int = None):
        """Assigns the franchise, tier, and league role to a user when they are drafted and posts to the assigned channel"""
        franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, team_name)
        gm_name = self.get_gm_name(ctx, franchise_role)
        if franchise_role in user.roles:
            message = "Round {0} Pick {1}: {2} was kept by the {3} ({4} - {5})".format(round, pick, user.mention, team_name, gm_name, tier_role.name)
        else:
            message = "Round {0} Pick {1}: {2} was drafted by the {3} ({4} - {5})".format(round, pick, user.mention, team_name, gm_name, tier_role.name)

        trans_channel = await self._trans_channel(ctx.guild)
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
    async def sign(self, ctx: Context, user: discord.Member, team_name: str):
        """Assigns the team role, franchise role and prefix to a user when they are signed and posts to the assigned channel"""
        franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, team_name)
        if franchise_role in user.roles and tier_role in user.roles:
            await ctx.send(":x: {0} is already on the {1}".format(user.mention, team_name))
            return

        trans_channel = await self._trans_channel(ctx.guild)
        if trans_channel is not None:
           try:
               await self.add_player_to_team(ctx, user, team_name)
               free_agent_roles = await self.find_user_free_agent_roles(ctx, user)
               if len(free_agent_roles) > 0:
                   for role in free_agent_roles:
                       await user.remove_roles(role)
               gm_name = self.get_gm_name(ctx, franchise_role)
               message = "{0} was signed by the {1} ({2} - {3})".format(user.mention, team_name, gm_name, tier_role.name)
               await trans_channel.send(message)
               await ctx.send("Done")
           except Exception as e:
               await ctx.send(e)

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def cut(self, ctx: Context, user : discord.Member, team_name: str, tier_fa_role: discord.Role = None):
        """Removes the team role and franchise role. Adds the free agent prefix and role to a user and posts to the assigned channel"""
        franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, team_name)
        trans_channel = await self._trans_channel(ctx.guild)
        if trans_channel is not None:
            try:
                await self.remove_player_from_team(ctx, user, team_name)
                if not self.team_manager_cog.is_gm(user):
                    if tier_fa_role is None:
                        role_name = "{0}FA".format((await self.team_manager_cog.get_current_tier_role(ctx, user)).name)
                        tier_fa_role = self.team_manager_cog._find_role_by_name(ctx, role_name)
                    fa_role = self.team_manager_cog._find_role_by_name(ctx, "Free Agent")
                    await self.team_manager_cog._set_user_nickname_prefix(ctx, "FA", user)
                    await user.add_roles(tier_fa_role, fa_role)
                gm_name = self.get_gm_name(ctx, franchise_role)
                message = "{0} was cut by the {1} ({2} - {3})".format(user.mention, team_name, gm_name, tier_role.name)
                await trans_channel.send(message)
                await self.maybe_send_dev_league_dm(ctx, user, tier_role)
                await ctx.send("Done")
            except KeyError:
                await ctx.send(":x: Free agent role not found in dictionary")
            except LookupError:
                await ctx.send(":x: Free agent role not found in server")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def trade(self, ctx: Context, user: discord.Member, new_team_name: str, user_2: discord.Member, new_team_name_2: str):
        """Swaps the teams of the two players and announces the trade in the assigned channel"""
        franchise_role_1, tier_role_1 = await self.team_manager_cog._roles_for_team(ctx, new_team_name)
        franchise_role_2, tier_role_2 = await self.team_manager_cog._roles_for_team(ctx, new_team_name_2)
        gm_name_1 = self.get_gm_name(ctx, franchise_role_1)
        gm_name_2 = self.get_gm_name(ctx, franchise_role_2)
        if franchise_role_1 in user.roles and tier_role_1 in user.roles:
            await ctx.send(":x: {0} is already on the {1}".format(user.mention, new_team_name))
            return
        if franchise_role_2 in user_2.roles and tier_role_2 in user_2.roles:
            await ctx.send(":x: {0} is already on the {1}".format(user_2.mention, new_team_name_2))
            return

        trans_channel = await self._trans_channel(ctx.guild)
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
    async def sub(self, ctx: Context, user: discord.Member, team_name: str, subbed_out_user: discord.Member = None):
        """
        Adds the team roles to the user and posts to the assigned transaction channel
        
        This command is also used to end substitution periods"""
        trans_channel = await self._trans_channel(ctx.guild)
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
                    gm = self.get_gm_name(ctx, franchise_role, True)
                    message = "{0} has finished their time as a substitute for the {1} ({2} - {3})".format(user.name, team_name, gm, team_tier_role.name)
                    # Removed subbed out role from all team members on team
                    subbed_out_role = self.team_manager_cog._find_role_by_name(ctx, self.SUBBED_OUT_ROLE)
                    if subbed_out_role:
                        team_members = self.team_manager_cog.members_from_team(ctx, franchise_role, team_tier_role)
                        for team_member in team_members:
                            await team_member.remove_roles(subbed_out_role)
                    # Reset player temp rating if the player rating cog is used
                    player_ratings: PlayerRatings = self.bot.get_cog("PlayerRatings")
                    if player_ratings:
                        await player_ratings.reset_temp_rating(ctx.guild, user)
                
                # Begin Substitution:
                else:
                    if free_agent_role in user.roles:
                        player_tier = await self.get_tier_role_for_fa(ctx, user)
                        await user.remove_roles(player_tier)
                    await user.add_roles(franchise_role, team_tier_role, leagueRole)
                    gm = self.get_gm_name(ctx, franchise_role)
                    message = "{0} was signed to a temporary contract by the {1} ({2} - {3})".format(user.mention, team_name, gm, team_tier_role.name)
                    # Give subbed out user the subbed out role if there is one
                    subbed_out_role = self.team_manager_cog._find_role_by_name(ctx, self.SUBBED_OUT_ROLE)
                    if subbed_out_user and subbed_out_role:
                        await subbed_out_user.add_roles(subbed_out_role)
                        player_ratings: PlayerRatings = self.bot.get_cog("PlayerRatings")
                        if player_ratings:
                            await player_ratings.set_player_temp_rating(ctx.guild, user, subbed_out_user)
                    elif subbed_out_user:
                        await ctx.send(":x: The subbed out role is not set in this server")
                await trans_channel.send(message)
                await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def promote(self, ctx: Context, user: discord.Member, team_name: str):
        """Adds the team tier role to the user and posts to the assigned channel"""
        old_team_name = await self.team_manager_cog.get_current_team_name(ctx, user)
        if old_team_name is not None:
            if (await self.team_manager_cog._roles_for_team(ctx, old_team_name))[0] != (await self.team_manager_cog._roles_for_team(ctx, team_name))[0]:
                await ctx.send(":x: {0} is not in the same franchise as {1}'s current team, the {2}".format(team_name.name, user.name, old_team_name))
                return
            
            trans_channel = await self._trans_channel(ctx.guild)
            if trans_channel:
                await self.remove_player_from_team(ctx, user, old_team_name)
                await self.add_player_to_team(ctx, user, team_name)
                franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, team_name)
                gm_name = self.get_gm_name(ctx, franchise_role)
                message = "{0} was promoted to the {1} ({2} - {3})".format(user.mention, team_name, gm_name, tier_role.name)
                await trans_channel.send(message)
                await ctx.send("Done")
        else:
            await ctx.send("Either {0} isn't on a team right now or his current team can't be found".format(user.name))

    #region get and set commands

    @commands.guild_only()
    @commands.command(aliases=["setTransChannel"])
    @checks.admin_or_permissions(manage_guild=True)
    async def setTransactionChannel(self, ctx: Context, trans_channel: discord.TextChannel):
        """Sets the channel where all transaction messages will be posted"""
        await self._save_trans_channel(ctx.guild, trans_channel.id)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command(aliases=["getTransChannel"])
    @checks.admin_or_permissions(manage_guild=True)
    async def getTransactionChannel(self, ctx: Context):
        """Gets the channel currently assigned as the transaction channel"""
        try:
            await ctx.send("Transaction log channel set to: {0}".format((await self._trans_channel(ctx.guild)).mention))
        except:
            await ctx.send(":x: Transaction log channel not set")

    @commands.guild_only()
    @commands.command(aliases=["unsetTransChannel"])
    @checks.admin_or_permissions(manage_guild=True)
    async def unsetTransactionChannel(self, ctx: Context):
        """Unsets the transaction channel. Transactions will not be performed if no transaction channel is set"""
        await self._save_trans_channel(ctx.guild, None)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command(aliases=["edl", "enableDevLeagueTier", "enableDevLeagueTiers", "addDevLeagueTier", "addDevLeagueTiers"])
    @checks.admin_or_permissions(manage_guild=True)
    async def enableDevLeague(self, ctx: Context, *, tiers):
        dev_league_tiers = await self._dev_league_tiers(ctx.guild)
        league_tiers = await self.team_manager_cog.tiers(ctx)
        added = []
        for tier in tiers.split():
            if tier in league_tiers and tier not in dev_league_tiers:
                dev_league_tiers.append(tier)
                added.append(tier)

        if added:
            await self._save_dev_league_tiers(ctx.guild, dev_league_tiers)
            await ctx.send(":white_check_mark: The following tiers have been added to the development league ({}): {}".format(
                len(added), ', '.join(added)
            ))
        else:
            await ctx.send(":x: No valid tiers were provided")

    @commands.guild_only()
    @commands.command(aliases=["viewDevLeagues"])
    @checks.admin_or_permissions(manage_guild=True)
    async def getDevLeagues(self, ctx: Context):
        dev_league_tiers = await self._dev_league_tiers(ctx.guild)
        if dev_league_tiers:
            await ctx.send("The following tiers have development leagues ({}): {}".format(len(dev_league_tiers), ', '.join(dev_league_tiers)))
        else:
            await ctx.send(":x: No tiers have corresponding development leagues.")

    @commands.guild_only()
    @commands.command(aliases=["ddl", "disableDevLeagueTier", "disableDevLeagueTiers", "removeDevLeagueTier", "removeDevLeagueTiers"])
    @checks.admin_or_permissions(manage_guild=True)
    async def disableDevLeague(self, ctx: Context, *, tiers):
        dev_league_tiers = await self._dev_league_tiers(ctx.guild)
        league_tiers = await self.team_manager_cog.tiers(ctx)
        removed = []
        for tier in tiers.split():
            if tier in league_tiers and tier in dev_league_tiers:
                dev_league_tiers.remove(tier)
                removed.append(tier)

        if removed:
            await self._save_dev_league_tiers(ctx.guild, dev_league_tiers)
            await ctx.send(":white_check_mark: The following tiers have been added to the development league ({}): {}".format(
                len(removed), ', '.join(removed)
            ))
        else:
            await ctx.send(":x: No valid tiers were provided")
    
    @commands.guild_only()
    @commands.command(aliases=['devLeagueCutMessage'])
    @checks.admin_or_permissions(manage_guild=True)
    async def setDevLeagueCutMessage(self, ctx: Context):
        dlcm = await self._dev_league_cut_message(ctx.guild)
        message = "If a tier **does** have a development league, this message will be sent to cut players:\n\n{}".format(dlcm)
        await ctx.send(message)

        ndlcm = await self._no_dev_league_cut_message(ctx.guild)
        message = "If a tier **does not** have a development league, this message will be sent to cut players:\n\n{}".format(ndlcm)
        await ctx.send(message)

    @commands.guild_only()
    @commands.command(aliases=["dlcm"])
    @checks.admin_or_permissions(manage_guild=True)
    async def setDevLeagueCutMessage(self, ctx: Context, *, message):
        await self._save_dev_league_cut_message(ctx.guild, message)
        await ctx.send("Done")
    
    @commands.guild_only()
    @commands.command(aliases=["ndlcm"])
    @checks.admin_or_permissions(manage_guild=True)
    async def setNoDevLeagueCutMessage(self, ctx: Context, *, message):
        await self._save_no_dev_league_cut_message(ctx.guild, message)
        await ctx.send("Done")
    
    #endregion

#endregion

#region helper methods

    async def add_player_to_team(self, ctx: Context, user, team_name):
        franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, team_name)
        leagueRole = self.team_manager_cog._find_role_by_name(ctx, "League")
        if leagueRole is not None:
            prefix = await self.prefix_cog.get_franchise_prefix(ctx.guild, franchise_role)
            if prefix is not None:
                currentTier = await self.team_manager_cog.get_current_tier_role(ctx, user)
                if currentTier is not None and currentTier != tier_role:
                    await user.remove_roles(currentTier)
                await self.team_manager_cog._set_user_nickname_prefix(ctx, prefix, user)
                await user.add_roles(tier_role, leagueRole, franchise_role)

    async def remove_player_from_team(self, ctx: Context, user, team_name):
        franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, team_name)
        if franchise_role not in user.roles or tier_role not in user.roles:
            await ctx.send(":x: {0} is not on the {1}".format(user.mention, team_name))
            return

        if self.team_manager_cog.is_gm(user):
            # For GMs remove the tier role
            await user.remove_roles(tier_role)
        elif franchise_role is not None:
            # For regular players remove the franchise role
            await user.remove_roles(franchise_role)

    async def find_user_free_agent_roles(self, ctx: Context, user):
        free_agent_roles = await self.get_free_agent_roles(ctx)
        user_fa_roles = []
        if(len(free_agent_roles) > 0):
            for fa_role in free_agent_roles:
                for role in user.roles:
                    if role.id == fa_role.id:
                        user_fa_roles.append(role)
        return user_fa_roles

    async def get_free_agent_roles(self, ctx: Context):
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
    
    async def set_user_nickname_prefix(self, ctx: Context, prefix: str, user: discord.member):
        return self.team_manager_cog._set_user_nickname_prefix(ctx, prefix, user)

    async def get_tier_role_for_fa(self, ctx: Context, user : discord.Member):
        fa_roles = await self.find_user_free_agent_roles(ctx, user)
        standard_fa_role = self.team_manager_cog._find_role_by_name(ctx, "Free Agent")
        if standard_fa_role in fa_roles:
            fa_roles.remove(standard_fa_role)
        tier_role_name = fa_roles[0].name[:-2]
        tier_role = self.team_manager_cog._find_role_by_name(ctx, tier_role_name)
        return tier_role

    def get_gm_name(self, ctx: Context, franchise_role, returnNameAsString=False):
        gm = self.team_manager_cog._get_gm(ctx, franchise_role)
        if gm:
            if returnNameAsString:
                return gm.name
            else:
                return gm.mention
        else:
           return self.team_manager_cog._get_gm_name(franchise_role)

    async def maybe_send_dev_league_dm(self, ctx: Context, user, tier_role):
        dev_league_tiers = await self._dev_league_tiers(ctx.guild)
        if not dev_league_tiers:
            return
        
        if tier_role.name in dev_league_tiers:
            message = await self._dev_league_cut_message(ctx.guild)
        else:
            message = await self._no_dev_league_cut_message(ctx.guild)
        
        await self.send_member_message(ctx, user, message)
    
    async def send_member_message(self, ctx: Context, member, message):
        if not message:
            return False
        message_title = "**Message from {0}:**\n\n".format(ctx.guild.name)
        command_prefix = ctx.prefix
        message = message.replace('[p]', command_prefix)
        message = message_title + message
        try:
            await member.send(message)
        except:
            await ctx.send(":x: Couldn't send message to this member.")

#endregion

#region load/save methods

    async def _trans_channel(self, guild: discord.Guild):
        return guild.get_channel(await self.config.guild(guild).TransChannel())

    async def _save_trans_channel(self, guild: discord.Guild, trans_channel):
        await self.config.guild(guild).TransChannel.set(trans_channel)

    async def _dev_league_tiers(self, guild: discord.Guild):
        return await self.config.guild(guild).DevLeagueTiers()

    async def _save_dev_league_tiers(self, guild: discord.Guild, tiers):
        await self.config.guild(guild).DevLeagueTiers.set(tiers)
    
    async def _dev_league_cut_message(self, guild: discord.Guild):
        return await self.config.guild(guild).DevLeagueCutMessage()
    
    async def _save_dev_league_cut_message(self, guild: discord.Guild, message):
        await self.config.guild(guild).DevLeagueCutMessage.set(message)
    
    async def _no_dev_league_cut_message(self, guild: discord.Guild):
        return await self.config.guild(guild).NoDevLeagueCutMessage()

    async def _save_no_dev_league_cut_message(self, guild: discord.Guild, message):
        await self.config.guild(guild).NoDevLeagueCutMessage.set(message)
    
#endregion
