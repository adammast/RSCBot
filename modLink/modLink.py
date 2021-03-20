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
        for b_role in removed_roles:
            if b_role in added_roles:
                removed_roles.remove(b_role)
                added_roles.remove(b_role)
        
        # member_instances = await self._shared_guild_member_instances(before.mutual_guilds, before)

        # # this will try to add a role from one guild to another. TODO: get matching role from each guild as well.
        shared_role_names = await self._get_shared_role_names(before.guild)
        event_log_channel = await self._event_log_channel(before.guild)

        if not event_log_channel:
            return False

        await event_log_channel("Here")

        # Shared role removal
        for role in removed_roles:
            # for member in member_instances:
            #     await member.remove_roles(role)
            roles_to_remove = await self._shared_guild_role_instances(before.mutual_guilds, role.name) if role.name in shared_role_names else None
            if roles_to_remove:
                await after.remove_roles(*roles_to_remove)
                await event_log_channel.send("Removed shared role across all shared servers ({}): {}".format(len(before.mutual_guilds), ', '.join(roles_to_remove)))
        
        # Shared role addition
        for role in added_roles:
            # for member in member_instances:
            #     await member.add_roles(role)
            roles_to_add = await self._shared_guild_role_instances(before.mutual_guilds, role.name) if role.name in shared_role_names else None
            if roles_to_add:
                await after.add_roles(*roles_to_add)
                await event_log_channel.send("Added shared role across all shared servers ({}): {}".format(len(before.mutual_guilds), ', '.join(roles_to_add)))
        
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
    
    async def _shared_guild_role_instances(self, mutual_guilds, target_role_name):
        role_matches = []
        for guild in mutual_guilds:
            for role in guild.roles:
                if role.name == target_role_name:
                    role_matches.append(role)
                    if len(role_matches) == len(mutual_guilds):
                        return role_matches
        return role_matches   

    async def _process_nickname_update(self, before, after):
        pass

    async def _add_shared_role(self, guild, role_name: str):
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
