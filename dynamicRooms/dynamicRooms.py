
import discord
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks

defaults = {"Categories": []}


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
    async def clearDynamicCategory(self, ctx):
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

    async def _is_dynamic_vc(self, guild: discord.Guild, voice_channel: discord.VoiceChannel):
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
        if not await self._is_dynamic_vc(member.guild, voice_channel):
            return False
        
        if len(voice_channel.members) == 1:
            clone_vc = await voice_channel.clone()
            await clone_vc.edit(position=voice_channel.position)
            await self._move_to_last(voice_channel)

    async def _member_leaves_voice(self, member: discord.Member, voice_channel: discord.VoiceChannel):
        # remove if dynamic room is empty
        if await self._is_dynamic_vc(member.guild, voice_channel) and len(voice_channel.members) == 0:
            return await voice_channel.delete()


    async def _save_dynamic_categories(self, guild, categories):
        await self.config.guild(guild).Categories.set(categories)

    async def _get_dynamic_categories(self, guild):
        return await self.config.guild(guild).Categories()
