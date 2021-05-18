import discord
from datetime import datetime
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks

defaults = {"Guilds": [], "SharedRoles": ["Muted"], "EventLogChannel": None}


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
            rewards += self.TROPHY_EMOJI
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
        
    @commands.guild_only()
    @commands.command(aliases=['assignMedal', 'awardMedal'])
    @checks.admin_or_permissions(manage_guild=True)
    async def addMedal(self, ctx, *userList):
        """Adds a first place medal to each user passed in the userList"""
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
            rewards += self.FIRST_PLACE_EMOJI
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
        """Updates member nickname and shared roles when they join the discord guild from their active status in the guild network."""
        mutual_guilds = self._member_mutual_guilds(member)
        shared_role_names = await self._get_shared_role_names(member.guild)
        event_log_channel = await self._event_log_channel(member.guild)
        if not event_log_channel or not shared_role_names:
            return
    
        # check each mutual guild with event logs set
        mutual_guilds.remove(member.guild)
        for guild in mutual_guilds:
            guild_event_log_channel = await self._event_log_channel(guild)
            if guild_event_log_channel:
                guild_member = self._guild_member_from_id(guild, member.id)
                guild_prefix, guild_nick, guild_rewards = self._get_name_components(guild_member)

                if guild_nick != member.name:
                    await member.edit(nick=guild_nick)
                    await event_log_channel.send("{} (**{}**) has had thier nickname set to **{}** upon joining the server [discovered from **{}**]".format(member.mention, member.name, guild_nick, guild.name))
                
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

    async def _save_event_log_channel(self, guild, event_channel):
        await self.config.guild(guild).EventLogChannel.set(event_channel)
        # await self.config.guild(ctx.guild).TransChannel.set(trans_channel)

    async def _event_log_channel(self, guild):
        return guild.get_channel(await self.config.guild(guild).EventLogChannel())

    async def _save_shared_roles(self, guild, shared_role_names):
        await self.config.guild(guild).SharedRoles.set(shared_roles)

    async def _get_shared_role_names(self, guild):
        return await self.config.guild(guild).SharedRoles()
