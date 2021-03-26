import discord
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks

defaults = {"Guilds": [], "SharedRoles": ["Muted"], "EventLogChannel": None}


class ModeratorLink(commands.Cog):
    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567892, force_registration=True)
        self.config.register_guild(**defaults)
        self.bot = bot

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
        
        if before_name != after_name:
            await self._process_nickname_update(before, after)
            
    @commands.Cog.listener("on_member_ban")
    async def on_member_ban(self, guild, user):
        for linked_guild in self.bot.guilds:
            linked_guild_log = await self._event_log_channel(linked_guild)
            is_banned = user in (banned_entry.user for banned_entry in await linked_guild.bans())
            if linked_guild_log and not is_banned:
                await linked_guild.ban(user, reason="Banned from {}.".format(guild.name), delete_message_days=0)
                await linked_guild_log.send("**{}** (id: {}) has been banned. [initiated from **{}**]".format(user.name, user.id, guild.name))
    
    @commands.Cog.listener("on_member_unban")
    async def on_member_unban(self, guild, user):
        for linked_guild in self.bot.guilds:
            linked_guild_log = await self._event_log_channel(linked_guild)
            is_banned = user in (banned_entry.user for banned_entry in await linked_guild.bans())
            if linked_guild_log and is_banned:
                await linked_guild.unban(user, reason="Unbanned from {}.".format(guild.name))
                await linked_guild_log.send("**{}** (id: {}) has been unbanned. [initiated from **{}**]".format(user.mention, user.id, guild.name))

    @commands.Cog.listener("on_member_join")
    async def on_member_join(self, member):
        mutual_guilds = def _member_mutual_guilds()


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
        before_name = before.nick if before.nick else before.name
        after_name = after.nick if after.nick else after.name
        
        event_log_channel = await self._event_log_channel(before.guild)

        before_nick = before_name[before_name.index(' | ')+3:] if ' | ' in before_name else before_name
        after_nick = after_name[after_name.index(' | ')+3:] if ' | ' in after_name else after_name

        if before_nick == after_nick or not event_log_channel:
            return
        
        mutual_guilds = self._member_mutual_guilds(before) # before.mutual_guilds not working
        mutual_guilds.remove(before.guild)

        for guild in mutual_guilds:
            channel = await self._event_log_channel(guild)
            if channel:
                member = self._guild_member_from_id(guild, before.id)
                name = member.nick if member.nick else member.name
                try:
                    prefix = name[0:name.index(' | ')] if ' | ' in name else ''
                    guild_before_name = member.nick if member.nick else member.name
                    guild_before_name = guild_before_name[guild_before_name.index(' | ')+3:] if ' | ' in guild_before_name else guild_before_name

                    if guild_before_name != after_nick:
                        if prefix:
                            await member.edit(nick='{} | {}'.format(prefix, after_nick))
                        else:
                            await member.edit(nick=after_nick)
                        await channel.send("{} has changed their name from **{}** to **{}** [initiated from **{}**]".format(member.mention, guild_before_name, after_nick, before.guild.name))
                except:
                    pass

    async def _save_event_log_channel(self, guild, event_channel):
        await self.config.guild(guild).EventLogChannel.set(event_channel)
        # await self.config.guild(ctx.guild).TransChannel.set(trans_channel)

    async def _event_log_channel(self, guild):
        return guild.get_channel(await self.config.guild(guild).EventLogChannel())

    async def _save_shared_roles(self, guild, shared_role_names):
        await self.config.guild(guild).SharedRoles.set(shared_roles)

    async def _get_shared_role_names(self, guild):
        return await self.config.guild(guild).SharedRoles()
