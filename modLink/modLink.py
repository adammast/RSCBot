import asyncio 
import discord
from datetime import date, datetime
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks

# Bot Detection
SPAM_JOIN_BT = "spam join"
SUS_NEW_ACC_BT = "suspicious new account"
NEW_MEMBER_JOIN_TIME = 300  # 5 minutes
ACC_AGE_THRESHOLD = 86400   # 1 day
DISABLE_BOT_INVITES = False

defaults = {
    "Guilds": [], 
    "SharedRoles": ["Muted"], 
    "EventLogChannel": None, 
    "BotDetection": False, 
    "WelcomeMessage": None,
    "BlacklistedNames": ["reward", "giveaway", "give away", "gift", "drop"]
}

class ModeratorLink(commands.Cog):
    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567892, force_registration=True)
        self.config.register_guild(**defaults)
        self.bot = bot

        self.TROPHY_EMOJI = "\U0001F3C6" # :trophy:
        self.GOLD_MEDAL_EMOJI = "\U0001F3C5" # gold medal
        self.FIRST_PLACE_EMOJI = "\U0001F947" # first place medal
        self.STAR_EMOJI = "\U00002B50" # :star:
        self.LEAGUE_REWARDS = [self.TROPHY_EMOJI, self.GOLD_MEDAL_EMOJI, self.FIRST_PLACE_EMOJI, self.STAR_EMOJI]
        self.whitelist = []
        self.bot_detection = {}
        self.recently_joined_members = {}
        asyncio.create_task(self._pre_load_data())

    def cog_unload(self):
        """Clean up when cog shuts down."""
        self.cancel_all_tasks()

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def toggleBotDetection(self, ctx):
        """Enables or disables bot dection for new member joins"""
        new_bot_detection_status = not (await self._get_bot_detection(ctx.guild))
        await self._save_bot_detection(ctx.guild, new_bot_detection_status)
        self.bot_detection[ctx.guild] = new_bot_detection_status

        if new_bot_detection_status:
            await self._pre_load_data()
        else:
            self.cancel_all_tasks(ctx.guild)

        action = "enabled" if new_bot_detection_status else "disabled"
        message = "Bot detection has been **{}** for this guild.".format(action)
        await ctx.send(message)
    
    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def whitelistUser(self, ctx, user_id: discord.User):
        """Allows a member to manually pass bot detection for 24 hours"""
        self.whitelist.append(user_id.id)
    
    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def blacklistName(self, ctx, *, name: str):
        """Adds a name to the bot account blacklist"""
        name = name.lower()
        blacklisted_names = await self._blacklisted_names(ctx.guild)
        if name not in blacklisted_names:
            blacklisted_names.append(name)
            await self._save_blacklisted_names(ctx.guild, blacklisted_names)
        
        await ctx.send("Done")
    
    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def unblacklistName(self, ctx, *, name: str):
        """Adds a name to the bot account blacklist"""
        blacklisted_names = await self._blacklisted_names(ctx.guild)
        if name.lower() in blacklisted_names:
            blacklisted_names.remove(name.lower())
            await self._save_blacklisted_names(ctx.guild, blacklisted_names)    
            return await ctx.send("Done")
        else:
            await ctx.send(":x: **{}** is not a blacklisted name.".format(name))

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setWelcomeMessage(self, ctx, *, welcome_message):
        """Sends a welcome message to the guild's system channel when a new member joins the guild.
        
        Notes:
         - Use `{member}` in your message in place of the newly added member (Optional)
         - Use `{guild}` in your message in place of the guild name (Optional)
         - Members or Roles mentioned in the message parameter will be pinged when a message is sent for a newly joined member

        __Examples:__
         - [p]setWelcomeMessage Hey {member}! Welcome to {guild}! We're happy to have you here.
         - [p]setWelcomeMessage @WelcomeCommittee we have a newcomer! Everyone welcome {member}! 
        """
        await self._save_welcome_message(ctx.guild, welcome_message)
        await ctx.send("Done")
    
    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearWelcomeMessage(self, ctx):
        """Clears welcome message set for the guild, disabling messages for new members."""
        await self._save_welcome_message(ctx.guild, None)
        await ctx.send("Done")
    
    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def getWelcomeMessage(self, ctx):
        """Gets welcome message set for the guild which is sent to newly joined members."""
        welcome_msg = await self._get_welcome_message(ctx.guild)
        if welcome_msg:
            await ctx.send("__Welcome Message:__\n{}".format(welcome_msg))
        else:
            await ctx.send(":x: No welcome message set.")
        
    @commands.guild_only()
    @commands.command(aliases=['setEventLogChannel'])
    @checks.admin_or_permissions(manage_guild=True)
    async def setEventChannel(self, ctx, event_channel: discord.TextChannel):
        """Sets the channel where all moderator-link related events are logged, and enables cross-guild member updates."""
        await self._save_event_log_channel(ctx.guild, event_channel.id)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command(aliases=['unsetEventLogChannel'])
    @checks.admin_or_permissions(manage_guild=True)
    async def unsetEventChannel(self, ctx):
        """Unsets the channel currently assigned as the event log channel and disables cross-guild member updates."""
        await self._save_event_log_channel(ctx.guild, None)
        await ctx.send("Event log channel has been cleared.")

    @commands.guild_only()
    @commands.command(aliases=['getEventLogChannel'])
    @checks.admin_or_permissions(manage_guild=True)
    async def getEventChannel(self, ctx):
        """Gets the channel currently assigned as the event log channel."""
        try:
            channel = await self._event_log_channel(ctx.guild)
            if channel:
                await ctx.send("Event log channel set to: {0}".format((channel).mention))
            else:
                await ctx.send("PepeHands.")
        except:
            await ctx.send(":x: Event log channel not set")

    @commands.guild_only()
    @commands.command(aliases=['champion', 'assignTrophy', 'awardTrophy'])
    @checks.admin_or_permissions(manage_guild=True)
    async def addTrophy(self, ctx, *userList):
        """Adds a trophy to each user passed in the userList"""
        await self.award_players(ctx, self.TROPHY_EMOJI, userList)

    @commands.guild_only()
    @commands.command(aliases=['allstar', 'assignStar', 'awardStar'])
    @checks.admin_or_permissions(manage_guild=True)
    async def addStar(self, ctx, *userList):
        """Adds a star to each user passed in the userList"""
        await self.award_players(ctx, self.STAR_EMOJI, userList)
        
    @commands.guild_only()
    @commands.command(aliases=['assignMedal', 'awardMedal'])
    @checks.admin_or_permissions(manage_guild=True)
    async def addMedal(self, ctx, *userList):
        """Adds a first place medal to each user passed in the userList"""
        await self.award_players(ctx, self.FIRST_PLACE_EMOJI, userList)

    # @commands.guild_only()
    # @commands.command()
    # @checks.admin_or_permissions(manage_guild=True)
    # async def ban(self, ctx, user: discord.User, *, reason=None):
    #     await ctx.guild.ban(user, reason=reason, delete_message_days=0)
    #     await ctx.send("Done.")
    
    # @commands.guild_only()
    # @commands.command()
    # @checks.admin_or_permissions(manage_guild=True)
    # async def unban(self, ctx, user: discord.User, *, reason=None):
    #     await ctx.guild.unban(user, reason=reason)
    #     await ctx.send("Done.")

    @commands.Cog.listener("on_user_update")
    async def on_user_update(self, before, after):
        """Catches when a user changes their discord name or discriminator. [Not yet supported]"""
        if before.name != after.name:
            pass
        if before.discriminator != after.discriminator:
            pass

    @commands.Cog.listener("on_member_update")
    async def on_member_update(self, before, after):
        """Processes updates for roles or nicknames, and shares them across the guild network."""
        
        # If roles updated:
        if before.roles != after.roles:
            await self._process_role_update(before, after)
        
        # If nickname changed:
        try:
            before_name = before.nick
        except:
            before_name = before.name
        try:
            after_name = after.nick
        except:
            after_name = after.name
        
        seconds_in_server = (datetime.utcnow() - before.joined_at).seconds
        if before_name != after_name and seconds_in_server > 120:
            await self._process_nickname_update(before, after)
            
    @commands.Cog.listener("on_member_ban")
    async def on_member_ban(self, guild, user):
        """Upon a member ban, members in the guild network will be banned automatically."""
        if not await self._event_log_channel(guild):
            return
        for linked_guild in self.bot.guilds:
            linked_guild_log = await self._event_log_channel(linked_guild)
            is_banned = user in (banned_entry.user for banned_entry in await linked_guild.bans())
            if linked_guild_log and not is_banned:
                await linked_guild.ban(user, reason="Banned from {}.".format(guild.name), delete_message_days=0)
                await linked_guild_log.send("**{}** (id: {}) has been banned. [initiated from **{}**]".format(user.name, user.id, guild.name))
    
    @commands.Cog.listener("on_member_unban")
    async def on_member_unban(self, guild, user):
        """Upon a member unban, members in the guild network will be unbanned automatically."""
        if not await self._event_log_channel(guild):
            return
        for linked_guild in self.bot.guilds:
            linked_guild_log = await self._event_log_channel(linked_guild)
            is_banned = user in (banned_entry.user for banned_entry in await linked_guild.bans())
            if linked_guild_log and is_banned:
                await linked_guild.unban(user, reason="Unbanned from {}.".format(guild.name))
                await linked_guild_log.send("**{}** (id: {}) has been unbanned. [initiated from **{}**]".format(user.mention, user.id, guild.name))

    @commands.Cog.listener("on_member_join")
    async def on_member_join(self, member):
        """Processes events for when a member joins the guild such as welcome messages and 
        nickname standardization, and bot purging."""

        # Run bot detection if enabled
        if self.bot_detection[member.guild]:
            # Do not process member standardization if member has been detected as a bot
            if await self.run_bot_detection(member):
                return
        
        event_log_channel = await self._event_log_channel(member.guild)
        if event_log_channel:
            await self.process_member_standardization(member)
        
        # Send welcome message if one exists
        await self.maybe_send_welcome_message(member)
        

    async def process_member_standardization(self, member):
        mutual_guilds = self._member_mutual_guilds(member)
        shared_role_names = await self._get_shared_role_names(member.guild)
        event_log_channel = await self._event_log_channel(member.guild)
        mutual_guilds.remove(member.guild)
        for guild in mutual_guilds:
            guild_event_log_channel = await self._event_log_channel(guild)
            if guild_event_log_channel:
                guild_member = self._guild_member_from_id(guild, member.id)
                guild_prefix, guild_nick, guild_rewards = self._get_name_components(guild_member)

                if guild_nick != member.name:
                    await member.edit(nick=guild_nick)
                    await event_log_channel.send("{} (**{}**) has had thier nickname set to **{}** upon joining the server [discovered from **{}**]".format(member.mention, member.name, guild_nick, guild.name))
                
                if shared_role_names:
                    # if member has shared role
                    member_shared_roles = []
                    for guild_member_role in guild_member.roles:
                        if guild_member_role.name in shared_role_names:
                            sis_role = self._guild_sister_role(member.guild, guild_member_role)
                            if sis_role:
                                member_shared_roles.append(sis_role)
                    
                    if member_shared_roles:
                        await member.add_roles(*member_shared_roles)
                        await event_log_channel.send(
                            "{} had one or more shared roles assigned upon joining this server: {} [discovered from **{}**]".format(
                                member.mention, ', '.join(role.mention for role in member_shared_roles), guild.name
                            ))
                
                    return

    async def maybe_send_welcome_message(self, member):
        guild = member.guild
        welcome_msg = await self._get_welcome_message(guild)
        channel = guild.system_channel
        await channel.send("Nine is here")
        if channel and welcome_msg:
            await channel.send("Nine is here 2")
            mention_roles = True    # or roles<list>
            mention_users = True    # or members<list>
            allowed_mentions = discord.AllowedMentions(roles=guild.roles, users=mention_users)
            return await channel.send(welcome_msg.format(member=member.mention, guild=guild.name), allowed_mentions=allowed_mentions)
        await channel.send("No special message :(")
    
    #region bot detection
    async def create_invite(self, channel: discord.TextChannel, retry=0, retry_max=3):
        try:
            return await channel.create_invite(temporary=True) # , max_uses=1, ) # max_age=86400)
        except discord.HTTPException:
            # Try x more times
            if retry <= retry_max:
                return await self.create_invite(channel, retry+1, retry_max)
            else:
                return None
    
    async def run_bot_detection(self, member):
        # IGNORE WHITELISTED MEMBERS
        if member.id in self.whitelist:
            return False

        # SPAM JOIN PREVENTION
        repeat_recent_name = self.track_member_join(member)
            
        ## Kick/Ban first member when subsequent member flagged as bot
        if repeat_recent_name and len(self.recently_joined_members[member.guild][member.name]['members']) == 2:
            first_member = self.recently_joined_members[member.guild][member.name]['members'][0]
            await self.process_member_bot_kick(first_member, reason=(SPAM_JOIN_BT + " - catch first"))

        ## Kick/ban newly joined member
        if repeat_recent_name:
            await self.process_member_bot_kick(first_member, reason=SPAM_JOIN_BT)
            # TODO: save bot name as blacklisted name?
            return True

        # SUSPICIOUS NEW ACCOUNTS
        for blacklist_name in await self._get_blacklisted_names(member.guild):  # await self._get_name_blacklist():
            account_age = (datetime.uctnow() - member.created_at).seconds
            if blacklist_name in member.name.lower() and account_age <= ACC_AGE_THRESHOLD + 10:
                await self.process_member_bot_kick(member, reason=SUS_NEW_ACC_BT)
                return True
        return False

    async def _pre_load_data(self):
        await self.bot.wait_until_ready()
        self.whitelist = []
        self.bot_detection = {}
        self.recently_joined_members = {}
        for guild in self.bot.guilds:
            self.recently_joined_members[guild] = {}
            self.bot_detection[guild] = await self._get_bot_detection(guild)
    
    def track_member_join(self, member: discord.Member):
        member_join_data = self.recently_joined_members[member.guild].setdefault(member.name, {'members': [], 'timeout': None})
        member_join_data['members'].append(member)
        if member_join_data['timeout']:
            member_join_data['timeout'].cancel()

        member_join_data['timeout'] = asyncio.create_task(self.schedule_new_member_name_clear(member))
        self.recently_joined_members[member.guild][member.name] = member_join_data
        repeat_recent_name = len(member_join_data['members']) > 1

        return repeat_recent_name

    async def schedule_new_member_name_clear(self, member: discord.Member, time_sec: int=None):
        if not time_sec:
            time_sec = NEW_MEMBER_JOIN_TIME
        await asyncio.sleep(time_sec)
        self.recently_joined_members[member.guild][member.name]['timeout'].cancel()
        del self.recently_joined_members[member.guild][member.name]

    async def process_member_bot_kick(self, member: discord.Member, reason=None, ban=False):
        guild = member.guild
        channel = guild.system_channel
        owner = guild.owner
        if channel:
            invite = await self.create_invite(channel)
        else:
            invite = None

        action = "banned" if ban else "kicked"
        message = ("You have been flagged as a bot account and **{}** from **{}**. "
                + "If this was a mistake, please send a message to **{}#{}**.".format(
                    action, guild.name, owner.name, owner.discriminator
                ))

        # TODO: save invite as "trusted" invite
        if invite:
            message += "Alternatively, you can wait 5 minutes, then [Click Here]({}) to rejoin the guild! We aplogize for the inconvenience.".format(invite.url)

        reason_note = "suspected bot"
        if reason:
            reason_note += ": {}".format(reason)
        embed = discord.Embed(
            title="Message from {}".format(guild.name),
            discriminator=message,
            colo=discord.Color.red()
        )
        embed.set_thumbnail(url=guild.icon_url)

        # Send message to kicked/banned member
        try:
            await member.send(embed=embed)
        except:
            pass

        # Kick or Ban members, log if even log channel is set
        try:
            if ban:
                await member.ban(reason=reason_note, delete_message_days=7)
            else:
                await member.kick(reason=reason_note, delete_message_days=7)
            event_log_channel = await self._event_log_channel(member.guild)
            if event_log_channel:
                await event_log_channel.send("**{}** (id: {}) has been flagged as a bot account and **{}** from the server (Reason: {}).".format(
                    member.name, member.id, action, reason
                ))
        except:
            pass

    def cancel_all_tasks(self, guild=None):
        guilds = [guild] if guild else self.bot.guilds
        for guild in guilds:
            for name, join_data in self.recently_joined_members[guild].items():
                join_data['timeout'].cancel()
            self.recently_joined_members[guild] = {}

    #endregion bot detection

    async def award_players(self, ctx, award, userList):
        found = []
        notFound = []
        success_count = 0
        failed = 0
        for user in userList:
            try:
                member = await commands.MemberConverter().convert(ctx, user)
                if member in ctx.guild.members:
                    found.append(member)
            except:
                notFound.append(user)
        
        for player in found:
            prefix, nick, rewards = self._get_name_components(player)
            rewards += award
            new_name = self._generate_new_name(prefix, nick, rewards)
            try:
                await player.edit(nick=new_name)
                success_count += 1
            except:
                failed += 1
        
        message = ""
        if success_count:
            message = ":white_check_mark: Trophies have been added to **{} player(s)**.".format(success_count)
        
        if notFound:
            message += "\n:x: {} members could not be found.".format(len(notFound))
        
        if failed:
            message += "\n:x: Nicknames could not be changed for {} members.".format(failed)
        
        if message:
            message += "\nDone"
        else:
            message = "No members changed."

        await ctx.send(message)

    async def _process_role_update(self, before, after):
        removed_roles = before.roles
        added_roles = after.roles
        intersect_roles = list(set(removed_roles)&set(added_roles))
        for r in intersect_roles:
            removed_roles.remove(r)
            added_roles.remove(r)
        
        # # this will try to add a role from one guild to another. TODO: get matching role from each guild as well.
        shared_role_names = await self._get_shared_role_names(before.guild)
        event_log_channel = await self._event_log_channel(before.guild)

        if not event_log_channel:
            return False

        # Filter role updates by shared roles
        for r in removed_roles:
            if r.name not in shared_role_names:
                removed_roles.remove(r)
        for r in added_roles:
            if r.name not in shared_role_names:
                added_roles.remove(r)

        mutual_guilds = self._member_mutual_guilds(before) # before.mutual_guilds not working
        mutual_guilds.remove(before.guild)

        if not removed_roles and not added_roles:
            return

        # Process Role Removals
        role_removal_msg = "Shared role {} removed from **{}** [initiated from **{}**]"
        for role in removed_roles:
            for guild in mutual_guilds:
                guild_role = self._guild_sister_role(guild, role)
                guild_member = self._guild_member_from_id(guild, before.id)
                channel = await self._event_log_channel(guild_member.guild)
                if guild_role in guild_member.roles and channel:
                    await guild_member.remove_roles(guild_role)
                    await channel.send(role_removal_msg.format(guild_role.mention, guild_member.mention, before.guild.name))

        # Process Role Additions
        role_assign_msg = "Shared role {} added to {} [initiated from **{}**]"
        for role in added_roles:
            for guild in mutual_guilds:
                guild_role = self._guild_sister_role(guild, role)
                guild_member = self._guild_member_from_id(guild, before.id)
                channel = await self._event_log_channel(guild_member.guild)
                if guild_role not in guild_member.roles and channel:
                    await guild_member.add_roles(guild_role)
                    await channel.send(role_assign_msg.format(guild_role.mention, guild_member.mention, before.guild.name))

    def _guild_member_from_id(self, guild, member_id):
        return guild.get_member(member_id)
    
    def _guild_role_from_name(self, guild, role_name):
        for member in guild.roles:
            if role.name == role_name:
                return role
    
    def _member_mutual_guilds(self, member):
        mutual_guilds = []
        for guild in self.bot.guilds:
            if member in guild.members:
                mutual_guilds.append(guild)
        return mutual_guilds

    def _guild_sister_role(self, guild, sister_role):
        for role in guild.roles:
            if role.name == sister_role.name and role != sister_role:
                return role
        return None

    async def _process_nickname_update(self, before, after):
        b_prefix, b_nick, b_rewards = self._get_name_components(before)
        a_prefix, a_nick, a_rewards = self._get_name_components(after)
        event_log_channel = await self._event_log_channel(before.guild)

        if b_nick == a_nick or not event_log_channel:
            return
        
        mutual_guilds = self._member_mutual_guilds(before) # before.mutual_guilds not working
        mutual_guilds.remove(before.guild)

        for guild in mutual_guilds:
            channel = await self._event_log_channel(guild)
            if channel:
                guild_member = self._guild_member_from_id(guild, before.id)
                guild_prefix, guild_nick, guild_rewards = self._get_name_components(guild_member)
                try:
                    if guild_nick != a_nick:
                        new_guild_name = self._generate_new_name(guild_prefix, a_nick, guild_rewards)
                        await guild_member.edit(nick=new_guild_name)
                        await channel.send("{} has changed their name from **{}** to **{}** [initiated from **{}**]".format(guild_member.mention, guild_nick, a_nick, before.guild.name))
                except:
                    pass

    def _get_name_components(self, member: discord.Member):
        if member.nick:
            name = member.nick
        else:
            return "", member.name, ""
        prefix = name[0:name.index(' | ')] if ' | ' in name else ''
        if prefix:
            name = name[name.index(' | ')+3:]
        player_name = ""
        rewards = ""
        for char in name[::-1]:
            if char not in self.LEAGUE_REWARDS:
                break
            rewards = char + rewards

        player_name = name.replace(" " + rewards, "") if rewards else name

        return prefix.strip(), player_name.strip(), rewards.strip()

    def _generate_new_name(self, prefix, name, rewards):
        new_name = "{} | {}".format(prefix, name) if prefix else name
        if rewards:
            new_name += " {}".format(rewards)
        return new_name

    #region json data
    async def _get_bot_detection(self, guild: discord.Guild):
        return await self.config.guild(guild).BotDetection()

    async def _save_bot_detection(self, guild: discord.Guild, bot_detection: bool):
        await self.config.guild(guild).BotDetection.set(bot_detection)

    async def _get_welcome_message(self, guild: discord.Guild):
        return await self.config.guild(guild).WelcomeMessage()

    async def _save_welcome_message(self, guild: discord.Guild, message: str):
        await self.config.guild(guild).WelcomeMessage.set(message)

    async def _get_blacklisted_names(self, guild: discord.Guild):
        return await self.config.guild(guild).BlacklistedNames()

    async def _save_blacklisted_names(self, guild: discord.Guild, name: str):
        await self.config.guild(guild).BlacklistedNames.set(name)

    async def _save_event_log_channel(self, guild, event_channel):
        await self.config.guild(guild).EventLogChannel.set(event_channel)
        # await self.config.guild(ctx.guild).TransChannel.set(trans_channel)

    async def _event_log_channel(self, guild):
        return guild.get_channel(await self.config.guild(guild).EventLogChannel())

    async def _save_shared_roles(self, guild, shared_role_names):
        await self.config.guild(guild).SharedRoles.set(shared_roles)

    async def _get_shared_role_names(self, guild):
        return await self.config.guild(guild).SharedRoles()
    #endregion json data