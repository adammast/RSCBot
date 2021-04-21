
import discord
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks

defaults = {"DynamicCategories": [], "DynamicRooms": [], "HideoutCategories": [], "HideoutRooms": [], "Hiding": []}


class DynamicRooms(commands.Cog):
    """Allows configuration of setting up dynamic rooms"""

    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567892, force_registration=True)
        self.config.register_guild(**defaults)
    

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def addDynamicCategory(self, ctx, category: discord.CategoryChannel):
        """Sets existing category where each contained voice channel will become a dynamic voice channel.
        """
        categories = await self._get_dynamic_categories(ctx.guild)
        categories.append(category.id)
        await self._save_dynamic_categories(ctx.guild, categories)

        await ctx.send("Done")

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


    @commands.command(aliases=['hide', 'hideus'])
    @commands.guild_only()
    async def hideme(self, ctx):
        await ctx.message.delete()
        member = ctx.message.author
        if not member.voice:
            await ctx.send("{}, you must be connected to a voice channel for that command to work.".format(member.mention))
            return
        
        vc = member.voice.channel
        if not await self._is_dynamic_vc(vc):
            # create replacement clone
            vc_clone = await vc.clone()
            await vc_clone.edit(position=vc.position)

        # hide current vc
        await vc.set_permissions(ctx.guild.default_role, view_channel=False)
        await vc.edit(name="{} (hidden)".format(vc.name))

        # update hiding vc list
        hiding_rooms = await self._get_hiding(ctx.guild)
        

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


    def _get_category_name(self, ctx, category_id):
        for category in ctx.guild.categories:
            if category.id == category_id:
                return "**{}** [{}]".format(category.name, category.id) 
        return None

    async def _is_dynamic_vc(self, voice_channel: discord.VoiceChannel):
        guild = voice_channel.guild
        dynamic_categories = await self._get_dynamic_categories(guild)
        if not dynamic_categories:
            return False
        return voice_channel.category_id in dynamic_categories

    async def _move_to_last(self, voice_channel: discord.VoiceChannel):
        last_index = voice_channel.position
        for vc in voice_channel.category.channels:
            if vc.position > last_index:
                last_index = vc.position
        
        if last_index > voice_channel.position:
            await voice_channel.edit(position=last_index+3) # 3 is an arbitrary number to cover a race condition - sometimes moves to 2nd last

    async def _member_joins_voice(self, member: discord.Member, voice_channel: discord.VoiceChannel):
        if not await self._is_dynamic_vc(voice_channel):
            return False
        
        if len(voice_channel.members) == 1:
            clone_vc = await voice_channel.clone()
            await clone_vc.edit(position=voice_channel.position)
            await self._move_to_last(voice_channel)

    async def _member_leaves_voice(self, member: discord.Member, voice_channel: discord.VoiceChannel):
        # no behavior for rooms that are still populated
        if len(voice_channel.members):
            return
        
        # remove if dynamic room is empty
        if await self._is_dynamic_vc(voice_channel) and len(voice_channel.members) == 0:
            return await voice_channel.delete()

    # JSON db interfaces
    async def _save_dynamic_categories(self, guild, categories):
        await self.config.guild(guild).DynamicCategories.set(categories)

    async def _get_dynamic_categories(self, guild):
        return await self.config.guild(guild).DynamicCategories()

    async def _save_dynamic_rooms(self, guild, rooms):
        await self.config.guild(guild).DynamicRooms.set(categories)

    async def _get_dynamic_rooms(self, guild):
        return await self.config.guild(guild).DynamicRooms()

    # Categories where rooms hide when full
    async def _save_hideout_categories(self, guild, categories):
        await self.config.guild(guild).HideoutCategories.set(categories)

    async def _get_hideout_categories(self, guild):
        return await self.config.guild(guild).HideoutCategories()

    # Rooms that hide when full - independent from category
    async def _save_hideout_rooms(self, guild, rooms):
        await self.config.guild(guild).HideoutRooms.set(rooms)

    async def _get_hideout_rooms(self, guild):
        return await self.config.guild(guild).HideoutRooms()

    # Rooms that hide upon command (<p>hide) => maybe merge with hideout rooms
    async def _save_hiding(self, guild, hidden_rooms):
        await self.config.guild(guild).Hiding.set(hidden_rooms)

    async def _get_hiding(self, guild):
        return await self.config.guild(guild).Hiding()
    