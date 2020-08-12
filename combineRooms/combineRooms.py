import discord
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks

defaults = {"room_capacity": 10, "Categories": [], "public_combines": True, "acronym": "RSC"}


class CombineRooms(commands.Cog):
    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567892, force_registration=True)
        self.config.register_guild(**defaults)
        self.team_manager_cog = bot.get_cog("TeamManager")
    
    @commands.command(aliases=["startcombines"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def startCombines(self, ctx):
        if not await self._combine_category_ids(ctx.guild):
            await self._start_combines(ctx)
            await ctx.send("Combine Rooms have been created.")
            return True
        await ctx.send("Combine Rooms have already been created.")
    
    @commands.command(aliases=["stopcombines"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def stopCombines(self, ctx):
        if await self._combine_category_ids(ctx.guild):
            await self._stop_combines(ctx)
            await ctx.send("Combine Rooms have been removed.")
            return True
        await ctx.send("No Combine Rooms found.")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearcombines(self, ctx):
        await self._save_combine_category_ids(ctx.guild, [])
        await ctx.send("Done.")

    @commands.command(aliases=["setroomcap", "src"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def setRoomCapacity(self, ctx, size: int):
        """
        Sets the maximum number of members allowed in combine voice channels. (Default: 10)
        """
        if size < 2:
            await ctx.send(":x: There is a minimum of 2 players per voice channel.")
            return False

        await self._update_combine_rooms(ctx, capacity=size)
        await self._save_room_capacity(ctx.guild, size)
        await ctx.send("Done")
        return True

    @commands.command(aliases=["roomcap", "grc"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def getRoomCapacity(self, ctx):
        """
        Gets the current capacity of combine voice rooms (Default: 10)
        This capacity is for all members, players and scouts combined.
        """
        cap = await self._room_capacity(ctx.guild)
        await ctx.send("Combines currently have a maximum size of {0} members.".format(cap))
        return

    @commands.command(aliases=["combinePublicity", "checkCombinePublicity", "ccp", "combineStatus", "checkCombineStatus", "ccs"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def getCombinePublicity(self, ctx):
        """
        Gets the current status (public/private) of the combines.
        If combines are **Public**, any member may participate.
        If combines are **Private**, only members with the "League" role may particpate.
        """
        public_str = "public" if await self._is_public_combine(ctx.guild) else "private"
        response = "Combines are currently **{0}**.".format(public_str)
        await ctx.send(response)

    @commands.command(aliases=["acronym"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def getAcronym(self, ctx):
        """
        Gets the acronym registered for combines. (Default: RSC)
        """
        acronym = await self._get_acronym(ctx.guild)
        await ctx.send("The acronym registered for the combines cog is **{0}**.".format(acronym))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def setAcronym(self, ctx, new_acronym: str):
        """
        Sets the server acronym used in the combines category. (Default: RSC)
        This is primarily used in #combine-details message
        """
        await self._update_combine_rooms(ctx, acronym=new_acronym)
        await self._save_acronym(ctx.guild, new_acronym)
        await ctx.send("The acronym has been registered as **{0}**.".format(new_acronym))

    @commands.command(aliases=["togglePub", "toggleCombines", "togglePublicCombine", "tpc", "toggleCombinePermissions", "tcp"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def togglePublicity(self, ctx):
        """
        Toggles the status (public/private) of the combines. (Default: Public)
        If combines are **Public**, any member may participate.
        If combines are **Private**, only members with the "League" role may particpate.
        """
        is_public = await self._toggle_public_combine(ctx.guild)

        public_str = "public" if is_public else "private"
        response = "Combines are now **{0}**.".format(public_str)
        await ctx.send(response)


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
        await self._save_combine_category_ids(ctx.guild, categories)
        return True
        
    async def _stop_combines(self, ctx):
        # remove combines channels, category
        saved_categories = await self._combine_category_ids(ctx.guild)
        for category in ctx.guild.categories:
            if category.id in saved_categories:
                for channel in category.channels:
                    await channel.delete()
                await category.delete()
        await self._save_combine_category_ids(ctx.guild, None)

    async def _add_combines_category(self, ctx, name: str):
        # check if category exists already
        league_role = self._get_role_by_name(ctx.guild, "League")
        is_public = await self._is_public_combine(ctx.guild)
        overwrites = {
            league_role: discord.PermissionOverwrite(view_channel=True, connect=True, send_messages=False),
            ctx.guild.default_role: discord.PermissionOverwrite(view_channel=is_public, connect=is_public, send_messages=False)
        }
        muted_role = self._get_role_by_name(ctx.guild, "Muted")
        if muted_role:
            overwrites[muted_role] = discord.PermissionOverwrite(connect=False)
        
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
                if this_number == previous_number + 1:
                    previous_number = this_number
                    previous_position = vc.position
                else:
                    break

        new_position = previous_position + 1
        new_room_number = previous_number + 1 
        new_room_name = "{0} // {1}{2}".format(tier, acronym.lower(), new_room_number)

        await category.create_voice_channel(new_room_name, permissions_synced=True, user_limit=capacity, position=new_position)

    async def _update_combine_rooms(self, ctx, acronym:str=None, capacity:int=None):
        categories = await self._combine_categories(ctx.guild)
        old_acronym = await self._get_acronym(ctx.guild)
        for tier_cat in categories:
            for vc in tier_cat.voice_channels:
                tier = self._get_category_tier(tier_cat)
                vc_name_substring = "{0} // {1}".format(tier, old_acronym.lower())
                if vc_name_substring in vc.name:
                    if acronym:
                        room_num = int(vc.name[len(vc_name_substring):])
                        new_room_name = "{0} // {1}{2}".format(tier, acronym.lower(), room_num)
                        await vc.edit(name=new_room_name)
                    if capacity:
                        await vc.edit(user_limit=capacity)

    async def _maybe_remove_combines_voice(self, guild: discord.Guild, tier: str, category: discord.CategoryChannel=None):
        acronym = await self._get_acronym(guild)
        empty_vcs = []
        for vc in category.voice_channels:
            if len(vc.members) ==  0 and "{0} // {1}".format(tier, acronym.lower()) in vc.name:
                empty_vcs.append(vc)

        for vc in empty_vcs[1:]:
            await vc.delete()

    async def _get_tier_category(guild: discord.Guild, tier: str):
        categories = await self._combine_category_ids(guild)
        for tier_cat in categories:
            if tier == tier_cat.name:
                return tier_cat
        return None

    async def _member_joins_voice(self, member: discord.Member, voice_channel: discord.VoiceChannel):
        categories = await self._combine_category_ids(member.guild)
        if not categories:
            return False
        
        if voice_channel.category_id in categories and len(voice_channel.members) == 1:
            tier_cat = self._get_category_by_id(member.guild, voice_channel.category_id)
            tier_str = self._get_category_tier(tier_cat)
            await self._add_combines_voice(member.guild, tier_str, tier_cat)
            return True
        return False

    async def _member_leaves_voice(self, member: discord.Member, voice_channel: discord.VoiceChannel):
        categories = await self._combine_category_ids(member.guild)
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

    async def _save_combine_category_ids(self, guild, categories):
        if categories:
            return await self.config.guild(guild).Categories.set(categories)
        return await self.config.guild(guild).Categories.set([])

    async def _combine_category_ids(self, guild):
        return await self.config.guild(guild).Categories()
   
    async def _combine_categories(self, guild):
        cat_ids = await self._combine_category_ids(guild)
        combine_categories = []
        for category in guild.categories:
            if category.id in cat_ids:
                combine_categories.append(category)
        return combine_categories

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
        
        #switch combine rooms publicity:
        league_role = self._get_role_by_name(guild, "League")
        for category in await self._combine_categories(guild):
            await category.set_permissions(guild.default_role, view_channel=not was_public, connect=not was_public, send_messages=False)
            await category.edit(sync_permissions=True)

        await self.config.guild(guild).public_combines.set(not was_public)
        return not was_public # is_public (after call)

    async def _is_public_combine(self, guild):
        return await self.config.guild(guild).public_combines()

    async def _save_acronym(self, guild, acronym: str):
        await self.config.guild(guild).acronym.set(acronym)

    async def _get_acronym(self, guild):
        return await self.config.guild(guild).acronym()