import discord
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks

defaults = {"Guilds": [], "SharedRoles": ["Muted"], "EventLogChannel": None, "ActionLogChannel": None}


class ModeratorLink(commands.Cog):
    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567892, force_registration=True)
        self.config.register_guild(**defaults)
        self.bot = bot

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setEventChannel(self, ctx, event_channel: discord.TextChannel):
        """Sets the channel where all moderator-link related events are logged, and enables cross-guild role sharing."""
        await self._save_event_log_channel(ctx.guild, event_channel.id)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def unsetEventChannel(self, ctx):
        """Gets the channel currently assigned as the event log channel"""
        await self._save_event_log_channel(ctx.guild, None)
        await ctx.send("Event log channel has been cleared.")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def getEventChannel(self, ctx):
        """Gets the channel currently assigned as the event log channel"""
        try:
            channel = await self._event_log_channel(ctx.guild)
            if channel:
                await ctx.send("Event log channel set to: {0}".format((channel).mention))
            else:
                await ctx.send("PepeHands.")
        except:
            await ctx.send(":x: Event log channel not set")
    

    @commands.Cog.listener("on_user_update")
    async def on_user_update(self, before, after):
        if before.username != after.username:
            pass
        if before.discriminator != after.discriminator:
            pass

    @commands.Cog.listener("on_member_update")
    async def on_member_update(self, before, after):
        if before.roles != after.roles:
            await self._process_role_update(before, after)
        # if before.nickname != after.nickname:
        #     await self._process_nickname_change(before, after)
            

    @commands.Cog.listener("on_member_ban")
    async def on_member_ban(self, guild, user):
        pass
    
    @commands.Cog.listener("on_member_unban")
    async def on_member_unban(self, guild, user):
        pass


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

        for r in removed_roles:
            if r.name not in shared_role_names:
                removed_roles.remove(r)
        for r in added_roles:
            if r.name not in shared_role_names:
                added_roles.remove(r)

        mutual_guilds = self._member_mutual_guilds(before) # before.mutual_guilds not working
        mutual_guilds.remove(before.guild)
        member_instances = await self._shared_guild_member_instances(mutual_guilds, before)

        for role in removed_roles:
            guild_role_instances = await self._shared_guild_role_instances(mutual_guilds, role)
            for guild_role in guild_role_instances:
                for guild_member in member_instances:
                    if guild_member.guild == guild_role.guild:
                        if guild_role in guild_member.roles:
                            await guild_member.remove_roles(guild_role)
                            channel = await self._event_log_channel(guild_member.guild)
                            await channel.send("Shared role **{}** removed from **{}** [initiated from **{}**]".format(guild_role.name, guild_member.name, before.guild.name))

        for role in added_roles:
            guild_role_instances = await self._shared_guild_role_instances(mutual_guilds, role)
            for guild_role in guild_role_instances:
                for guild_member in member_instances:
                    if guild_member.guild == guild_role.guild:
                        if guild_role not in guild_member.roles:
                            await guild_member.add_roles(guild_role)
                            channel = await self._event_log_channel(guild_member.guild)
                            await channel.send("Shared role **{}** added to **{}** [initiated from **{}**]".format(guild_role.name, guild_member.name, before.guild.name))
        
        await event_log_channel.send("Done.")

    # TODO: remove
    async def _shared_guild_member_instances(self, mutual_guilds, target_member):
        member_matches = []
        for guild in mutual_guilds:
            for member in guild.members:
                if member.id == target_member.id:
                    member_matches.append(member)
                    if len(member_matches) == len(mutual_guilds):
                        return member_matches
        return member_matches
    
    def _member_mutual_guilds(self, member):
        mutual_guilds = []
        for guild in self.bot.guilds:
            if member in guild.members:
                mutual_guilds.append(guild)
        return mutual_guilds

    async def _add_shared_role(self, mutual_guilds, target_member, target_role):
        shared = 0
        for guild in mutual_guilds:
            guild_role = None
            guild_member = None
            for role in guild.roles:
                if role.name == target_role.name:
                    guild_role = role
            for member in guild.members:
                if member.id == target_member.id:
                    guild_member = member
            
            if target_member and target_role:
                await target_member.add_roles(guild_role)
                shared += 1
        return shared

    async def _shared_guild_role_instances(self, mutual_guilds, target_role):
        role_matches = []
        for guild in mutual_guilds:
            for role in guild.roles:
                if role.name == target_role.name and role != target_role:
                    role_matches.append(role)
                    if len(role_matches) == len(mutual_guilds):
                        return role_matches
        return role_matches   

    async def _process_nickname_update(self, before, after):
        pass

    async def _add_shared_role_WHY_IS_THIS_HERE_IDK(self, guild, role_name: str):
        roles = self._get_shared_roles(guild)
        roles.append(role_name)
        await self.config.guild(guild).Roles.set(roles)

    async def _log_linked_event(self, source_guild, member, action: str):
        for guild in self.bot.guilds:
            event_log_channel = await self._event_log_channel()

    async def _save_event_log_channel(self, guild, event_channel):
        await self.config.guild(guild).EventLogChannel.set(event_channel)
        # await self.config.guild(ctx.guild).TransChannel.set(trans_channel)

    async def _event_log_channel(self, guild):
        return guild.get_channel(await self.config.guild(guild).EventLogChannel())

    async def _save_shared_roles(self, guild, shared_role_names):
        await self.config.guild(guild).SharedRoles.set(shared_roles)

    async def _get_shared_role_names(self, guild):
        return await self.config.guild(guild).SharedRoles()
