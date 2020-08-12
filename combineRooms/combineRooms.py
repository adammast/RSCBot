import discord
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks

defaults = {"players_per_room": 6, "room_capacity": 10, "Categories": [], "public_combines": True, "acronym": "RSC", "CustomMessage": None}


class CombineRooms(commands.Cog):
    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567892, force_registration=True)
        self.config.register_guild(**defaults)
        self.team_manager_cog = bot.get_cog("TeamManager")
    
    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def startcombines(self, ctx):
        if not await self._combines_categories(ctx.guild):
            await self._start_combines(ctx)
            await ctx.send("Combine Rooms have been created.")
            return True
        await ctx.send("Combine Rooms have already been created.")
    
    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def stopcombines(self, ctx):
        if await self._combines_categories(ctx.guild):
            await self._stop_combines(ctx)
            await ctx.send("Combine Rooms have been removed.")
            return True
        await ctx.send("No Combine Rooms found.")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearcombines(self, ctx):
        await self._save_combines_categories(ctx.guild, [])
        await ctx.send("Done.")


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

    

    async def _start_combines(self, ctx):
        # Creates a combines category and room for each tier
        # await self._add_combines_info_channel(ctx.guild, combines_category, "Combines Details")
        categories = []
        for tier in await self.team_manager_cog.tiers(ctx):
            tier_category = await self._add_combines_category(ctx, "{0} Combines".format(tier))
            await self._add_combines_voice(ctx.guild, tier, tier_category)
            categories.append(tier_category.id)
        await self._save_combines_categories(ctx.guild, categories)
        return True
        
    async def _stop_combines(self, ctx):
        # remove combines channels, category
        saved_categories = await self._combines_categories(ctx.guild)
        for category in ctx.guild.categories:
            if category.id in saved_categories:
                for channel in category.channels:
                    await channel.delete()
                await category.delete()
        await self._save_combines_categories(ctx.guild, None)

    async def _add_combines_category(self, ctx, name: str):
        # check if category exists already
        overwrites = {}
        muted_role = self._get_role_by_name(ctx.guild, "Muted")
        if muted_role:
            overwrites[muted_role] = discord.PermissionOverwrite(connect=False)
        
        if not await self._is_public_combine(ctx.guild):
            league_role = self._get_role_by_name(ctx.guild, "League")
            overwrites[ctx.guild.default_role] = discord.PermissionOverwrite(view_channel=False, connect=False, send_messages=False)
            overwrites[league_role] = discord.PermissionOverwrite(view_channel=True, connect=True, send_messages=False)

        return await ctx.guild.create_category(name, overwrites=overwrites)

    async def _add_combines_voice(self, guild: discord.Guild, tier: str, category: discord.CategoryChannel=None):
        if not category:
            category = await self._get_tier_category(guild, tier)
            if not category:
                return False
        # user_limit of 0 means there's no limit
        # determine position with same name +1
        previous_position = 0
        previous_number = 0
        acronym = await self._get_acronym(guild)
        capacity = await self._room_capacity(guild)
        
        for vc in category.voice_channels:
            vc_name_substring = "{0} // {1}".format(tier, acronym.lower())
            if vc_name_substring in vc.name:
                this_number = int(vc.name[len(vc_name_substring):])
                print(this_number)
                if this_number == previous_number + 1:
                    previous_number = this_number
                    previous_position = vc.position
                else:
                    break

        new_position = previous_position + 1
        new_room_number = previous_number + 1 
        new_room_name = "{0} // {1}{2}".format(tier, acronym.lower(), new_room_number)

        await category.create_voice_channel(new_room_name, permissions_synced=True, user_limit=capacity, position=new_position)

    async def _maybe_remove_combines_voice(self, guild: discord.Guild, tier: str, category: discord.CategoryChannel=None):
        empty_vcs = []
        for vc in category.voice_channels:
            if len(vc.members) ==  0 and "{0} // rsc".format(tier) in vc.name:
                empty_vcs.append(vc)

        for vc in empty_vcs[1:]:
            await vc.delete()

    async def _get_tier_category(guild: discord.Guild, tier: str):
        categories = await self._combines_categories(guild)
        for tier_cat in categories:
            if tier == tier_cat.name:
                return tier_cat
        return None

    async def _member_joins_voice(self, member: discord.Member, voice_channel: discord.VoiceChannel):
        categories = await self._combines_categories(member.guild)
        if not categories:
            return False
        
        if voice_channel.category_id in categories and len(voice_channel.members) == 1:
            tier_cat = self._get_category_by_id(member.guild, voice_channel.category_id)
            tier_str = self._get_category_tier(tier_cat)
            await self._add_combines_voice(member.guild, tier_str, tier_cat)
            return True
        return False

    async def _member_leaves_voice(self, member: discord.Member, voice_channel: discord.VoiceChannel):
        categories = await self._combines_categories(member.guild)
        if not categories:
            return False

        if voice_channel.category_id in categories and len(voice_channel.members) == 0:
            tier_cat = self._get_category_by_id(member.guild, voice_channel.category_id)
            tier_str = self._get_category_tier(tier_cat)
            await self._maybe_remove_combines_voice(member.guild, tier_str, tier_cat)
            return True
        return False
     
    def _get_role_by_name(self, guild: discord.Guild, name: str):
        for role in guild.roles:
            if role.name == name:
                return role
        return None

    async def _save_combines_categories(self, guild, categories):
        if categories:
            return await self.config.guild(guild).Categories.set(categories)
        return await self.config.guild(guild).Categories.set([])

    async def _combines_categories(self, guild):
        return await self.config.guild(guild).Categories()
   
    def _get_category_by_id(self, guild, category_id):
        for category in guild.categories:
            if category.id == category_id:
                return category
        return None

    def _get_category_tier(self, category: discord.CategoryChannel):
        return category.name[:category.name.index(" ")]

    async def _room_capacity(self, guild):
        cap = await self.config.guild(guild).room_capacity()
        return cap if cap else 0

    async def _save_room_capacity(self, guild, capacity: int):
        await self.config.guild(guild).room_capacity.set(capacity)

    async def _toggle_public_combine(self, guild):
        was_public = await self._is_public_combine(guild)
        await self.config.guild(guild).public_combines.set(not was_public)
        return not was_public # is_public (after call)

    async def _is_public_combine(self, guild):
        return await self.config.guild(guild).public_combines()

    async def _save_acronym(self, guild, acronym: str):
        await self.config.guild(guild).acronym.set(acronym)

    async def _get_acronym(self, guild):
        return await self.config.guild(guild).acronym()