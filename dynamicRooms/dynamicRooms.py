
import discord
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks

defaults = {"DynamicCategories": [], "DynamicRooms": [], "HideoutCategories": [], "Hiding": [], "HideVCsEnabled": False}


class DynamicRooms(commands.Cog):
    """Allows configuration of setting up dynamic rooms and hideout"""

    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567892, force_registration=True)
        self.config.register_guild(**defaults)
    

    # Dynamic Categories - TODO: check category for dynamic rooms
    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def addDynamicCategory(self, ctx, category: discord.CategoryChannel):
        """Sets existing category where each contained voice channel will become a dynamic voice channel.
        """
        categories = await self._get_dynamic_categories(ctx.guild)
        if category not in categories:
            categories.append(category.id)
            await self._save_dynamic_categories(ctx.guild, categories)
            await ctx.send("Done")
        else:
            await ctx.send("This category is already dynamic.")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearDynamicCategories(self, ctx):
        """Disables dynamic room behavior of all categories.
        """
        await self._save_dynamic_categories(ctx.guild, [])
        await ctx.send("Done")
    
    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def getDynamicCategories(self, ctx):
        """View all categories that are configured for dynamic room management.
        """
        categories = await self._get_dynamic_categories(ctx.guild)
        if not categories:
            return await ctx.send(":x: No dynamic categories set.")
        
        message = "The following categories have been set as dynamic:\n - " + "\n - ".join(self._get_category_name(ctx, c) for c in categories)
        await ctx.send(message)

    # Dynamic Rooms
    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def addDynamicRoom(self, ctx, voice_channel: discord.VoiceChannel):
        """Sets a voice channel to be dynamic. This is independent from a dynamic category.
        """
        categories = await self._get_dynamic_categories(ctx.guild)
        dynamic_vcs = await self._get_dynamic_rooms(ctx.guild)
        if not (voice_channel.id in categories or voice_channel.id in dynamic_vcs):
            dynamic_vcs.append(voice_channel.id)
            await self._save_dynamic_rooms(ctx.guild, dynamic_vcs)
            await ctx.send("Done")
        else:
            await ctx.send("This room is already dynamic.")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearDynamicRooms(self, ctx):
        """Disables dynamic room behavior of individual dynamic rooms.
        """
        await self._save_dynamic_rooms(ctx.guild, [])
        await ctx.send("Done")
    
    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def getDynamicRooms(self, ctx):
        """View all individiual voice channels that are configured for dynamic room management.
        """
        dynamic_vcs = await self._get_dynamic_rooms(ctx.guild)
        if not dynamic_vcs:
            return await ctx.send(":x: No individual dynamic rooms have been set.")
        
        message = "The following categories have been set as dynamic:\n - " + "\n - ".join(self._get_channel_name(ctx.guild, c) for c in dynamic_vcs)
        await ctx.send(message)

    # Hideout Categories
    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def addHideoutCategory(self, ctx, category: discord.CategoryChannel):
        """Sets existing category where each contained voice channel will be cloned and hidden when it reaches its capacity.
        """
        categories = await self._get_hideout_categories(ctx.guild)
        categories.append(category.id)
        await self._save_hideout_categories(ctx.guild, categories)

        await ctx.send("Done")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearHideoutCategories(self, ctx):
        """Disables hideout room behavior of all hideout categories.
        """
        await self._save_hideout_categories(ctx.guild, [])
        await ctx.send("Done")
    
    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def getHideoutCategories(self, ctx):
        """View all categories that are configured for hideout room management.
        """
        categories = await self._get_hideout_categories(ctx.guild)
        if not categories:
            return await ctx.send(":x: No hideout categories set.")
        
        message = "The following categories have been set as dynamic:\n - " + "\n - ".join(self._get_category_name(ctx, c) for c in categories)
        await ctx.send(message)

    # hide command
    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def getHiddenRooms(self, ctx):
        """View all individiual voice channels that are actively hidden.
        """
        hidden_vc_ids = await self._get_hiding(ctx.guild)
        print(hidden_vc_ids)
        if not hidden_vc_ids:
            return await ctx.send(":x: There are currently no hiding rooms.")
        
        message = "The following rooms are currently hidden ({}):\n - ".format(len(hidden_vc_ids)) + "\n - ".join(self._get_channel_name(ctx.guild, vc) for vc in hidden_vc_ids)
        await ctx.send("The following rooms are currently hidden ({}):\n - ".format(len(hidden_vc_ids)) + "\n - ".join(self._get_channel_name(ctx.guild, vc) for vc in hidden_vc_ids))
    
    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearDynamicVCData(self, ctx):
        """Clears all dynamic room data in the `dynamicRooms` cog"""
        await self._save_dynamic_categories(ctx.guild, [])
        await self._save_hiding(ctx.guild, [])
        await self._save_dynamic_rooms(ctx.guild, [])
        await ctx.send("Done")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def toggleHideoutVCs(self, ctx):
        """Enables or disables the `[p]hide` command"""
        was_enabled = await self._is_hide_enabled(ctx.guild)
        
        if was_enabled:
            await self._disable_hide_vcs(ctx.guild)
            action = 'disabled'
        else:
            await self._enable_hide_vcs(ctx.guild)
            action = 'enabled'

        await ctx.send("The `{}hide` command is **{}**.".format(ctx.prefix, action))
        
    @commands.command(aliases=['hideme', 'hideus'])
    @commands.guild_only()
    async def hide(self, ctx):
        """Hides the voice channel the invoker currently occupies from other members in the guild."""
        await ctx.message.delete()
        if not await self._is_hide_enabled(ctx.guild):
            return 

        member = ctx.message.author
        if not member.voice:
            await ctx.send("{}, you must be connected to a voice channel for that command to work.".format(member.mention))
            return
        
        if not await self._is_hideout_vc(member.voice.channel):
            await self._hide_vc(member.voice.channel)
    
    @commands.guild_only()
    @commands.Cog.listener("on_guild_channel_delete")
    async def on_guild_channel_delete(self, channel):
        """Removes channel from db if a channel is deleted."""
        if type(channel) != discord.VoiceChannel:
            return
        vc = channel
        dynamic_vc = await self._is_dynamic_vc(vc)
        hideout_vc = await self._is_hideout_vc(vc)
        if not (dynamic_vc or hideout_vc):
            return
        
        dynamic_vcs = await self._get_dynamic_rooms(vc.guild)
        if vc.id in dynamic_vcs:
            dynamic_vcs.remove(vc.id)
            await self._save_dynamic_rooms(vc.guild, dynamic_vcs)
        
        hidden_vcs = await self._get_hiding(vc.guild)
        if vc.id in hidden_vcs:
            hidden_vcs.remove(vc.id)
            await self._save_hiding(vc.guild, hidden_vcs)
        

    @commands.Cog.listener("on_voice_state_update")
    async def on_voice_state_update(self, member, before, after):
        # ignore when voice activity is within the same room
        if before.channel == after.channel:
            return
        
        # Room joined:
        if after.channel:
            await self._member_joins_voice(member, after.channel)
        
        # Room left:
        if before.channel:
            await self._member_leaves_voice(member, before.channel)

    
    async def _member_joins_voice(self, member: discord.Member, voice_channel: discord.VoiceChannel):
        dynamic_vc = await self._is_dynamic_vc(voice_channel)
        hideout_vc = await self._is_hideout_vc(voice_channel)
        if not (dynamic_vc or hideout_vc):
            return False
        
        if dynamic_vc:
            if len(voice_channel.members) == 1:
                clone_vc = await voice_channel.clone()
                await clone_vc.edit(position=voice_channel.position)
                if voice_channel.category and voice_channel.category.id in await self._get_dynamic_categories(member.guild):
                    await self._move_to_last(voice_channel)
                else:
                    dynamic_vcs = await self._get_dynamic_rooms(member.guild)
                    dynamic_vcs.append(clone_vc.id)
                    await self._save_dynamic_rooms(member.guild, dynamic_vcs)

        if hideout_vc and (not await self._is_hiding(voice_channel)) and len(voice_channel.members) == voice_channel.user_limit:
            await self._hide_vc(voice_channel)

    async def _member_leaves_voice(self, member: discord.Member, voice_channel: discord.VoiceChannel):
        # no behavior for rooms that are still populated
        if len(voice_channel.members):
            return
        
        # remove if dynamic or hideout room is empty
        dynamic_room = await self._is_dynamic_vc(voice_channel)
        if not (dynamic_room or await self._is_hideout_vc(voice_channel)):
            return

        await voice_channel.delete()


    def _get_category_name(self, ctx, category_id):
        for category in ctx.guild.categories:
            if category.id == category_id:
                return "**{}** [{}]".format(category.name, category.id) 
        return None
    
    def _get_channel_name(self, guild, channel_id):
        for channel in guild.channels:
            if channel.id == channel_id:
                return "**{}** [{}]".format(channel.name, channel.id) 
        return None

    async def _is_hideout_vc(self, voice_channel: discord.VoiceChannel):
        # guild = voice_channel.guild
        # hideout_categories = await self._get_hideout_categories(voice_channel.guild)
        hiding_vcs = await self._get_hiding(voice_channel.guild)

        return voice_channel.id in hiding_vcs # or voice_channel.category_id in hideout_categories
    
    async def _is_dynamic_vc(self, voice_channel: discord.VoiceChannel):
        guild = voice_channel.guild
        
        dynamic_categories = await self._get_dynamic_categories(guild)
        dynamic_vcs = await self._get_dynamic_rooms(guild)
        
        dynamic_category_vc = voice_channel.category_id in dynamic_categories
        stand_alone_dynamic_vc = voice_channel.id in dynamic_vcs
        
        return dynamic_category_vc or stand_alone_dynamic_vc

    # adds to hiding
    async def _hide_vc(self, vc: discord.VoiceChannel):
        if not await self._is_dynamic_vc(vc):
            # create replacement clone
            vc_clone = await vc.clone()
            await vc_clone.edit(position=vc.position)

        # hide current vc
        await vc.set_permissions(vc.guild.default_role, view_channel=False)

        cant_view_overwrite = discord.PermissionOverwrite(view_channel=False)
        voice_overwrites = {
            vc.guild.default_role: cant_view_overwrite
        }
        for role in vc.overwrites.keys():
            voice_overwrites[role] = cant_view_overwrite

        await vc.edit(name="{} (hidden)".format(vc.name), overwrites=voice_overwrites)

        # update hiding vc list
        hiding_rooms = await self._get_hiding(vc.guild)
        hiding_rooms.append(vc.id)
        await self._save_hiding(vc.guild, hiding_rooms)

    async def _move_to_last(self, voice_channel: discord.VoiceChannel):
        last_index = voice_channel.position
        for vc in voice_channel.category.channels:
            if vc.position > last_index:
                last_index = vc.position
        
        if last_index > voice_channel.position:
            await voice_channel.edit(position=last_index+3) # 3 is an arbitrary number to cover a race condition - sometimes moves to 2nd last

    # JSON db interfaces
    # Dynamic Categories
    async def _save_dynamic_categories(self, guild, categories):
        await self.config.guild(guild).DynamicCategories.set(categories)

    async def _get_dynamic_categories(self, guild):
        return await self.config.guild(guild).DynamicCategories()

    # Dynamic Rooms - independent from categories
    async def _save_dynamic_rooms(self, guild, vcs):
        await self.config.guild(guild).DynamicRooms.set(vcs)

    async def _get_dynamic_rooms(self, guild):
        return await self.config.guild(guild).DynamicRooms()

    # Categories where rooms hide when full
    async def _save_hideout_categories(self, guild, categories):
        await self.config.guild(guild).HideoutCategories.set(categories)

    async def _get_hideout_categories(self, guild):
        return await self.config.guild(guild).HideoutCategories()

    # Rooms that are actively hiding
    async def _save_hiding(self, guild, hidden_rooms):
        await self.config.guild(guild).Hiding.set(hidden_rooms)

    async def _get_hiding(self, guild):
        return await self.config.guild(guild).Hiding()
    
    async def _is_hiding(self, vc: discord.VoiceChannel):
        return vc.id in await self._get_hiding(vc.guild)

    # hide vc command settings
    async def _enable_hide_vcs(self, guild):
        await self.config.guild(guild).HideVCsEnabled.set(True)

    async def _disable_hide_vcs(self, guild):
        await self.config.guild(guild).HideVCsEnabled.set(False)

    async def _is_hide_enabled(self, guild):
        return await self.config.guild(guild).HideVCsEnabled()
