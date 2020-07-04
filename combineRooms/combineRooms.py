import discord
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks

# TODO:
# - custom combines_info message
defaults = {"players_per_room": 6, "room_capacity": 10, "combines_category": None, "public_combines": True, "acronym": "RSC"}


class CombineRooms(commands.Cog):
    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567892, force_registration=True)
        self.config.register_guild(**defaults)
        self.team_manager_cog = bot.get_cog("TeamManager")

    @commands.command(aliases=["startcombines", "stopcombines"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def combines(self, ctx, *keywords):
        """
        Creates rooms for combines, or tears them down depending on the action parameter. If no parameter is given, it will behave as a switch.
        
        Examples:
        [p]combines
        [p]combines start
        [p]combines stop
        """
        keywords = set(keywords)
        # is_public = not bool(keywords & set(["private"]))

        if bool(keywords & set(["start", "create"])):
            done = await self._start_combines(ctx)
        elif bool(keywords & set(["start", "create"])):
            done = await self._stop_combines(ctx)
        else:
            combines_ongoing = await self._combines_category(ctx.guild)
            if combines_ongoing:
                done = await self._stop_combines(ctx)
            else:
                done = await self._start_combines(ctx)
        if done:
            await ctx.send("Done")
        return
    
    @commands.command(aliases=["sppr"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def setPlayersPerRoom(self, ctx, size: int):
        """
        Sets the recommended amount of concurrent players in combine rooms. (Default: 6)
        """

        if size < 2:
            await ctx.send(":x: There is a minimum of 2 players per voice channel.")
            return False  
        combines_cat = await self._save_players_per_room(ctx.guild, size)
        # DISABLED: room size in name
        # if combines_cat and False:
        #     for vc in combines_cat.voice_channels:
        #         await self._adjust_room_(guild, vc)
        await ctx.send("Done")
        return True
    
    @commands.command(aliases=["ppr"])
    @commands.guild_only()
    async def getPlayersPerRoom(self, ctx):
        """
        Gets the recommended amount of concurrent players in combine rooms.
        """
        size = await self._players_per_room(ctx.guild)
        await ctx.send("Combines should have no more than {0} active players in them.".format(size))

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
        combines_cat = await self._save_room_capacity(ctx.guild, size)
        if self._combines_category(ctx.guild):
            await ctx.send("Done: Changes will not be applied to rooms that are already up.")
        else:
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
        await self._update_combine_permissions(ctx.guild)

        public_str = "public" if is_public else "private"
        response = "Combines are now **{0}**.".format(public_str)
        await ctx.send(response)

    @commands.command(aliases=["checkCombinePublicity", "ccp", "combineStatus", "checkCombineStatus", "ccs"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def combinePublicity(self, ctx):
        """
        Gets the current status (public/private) of the combines.
        If combines are **Public**, any member may participate.
        If combines are **Private**, only members with the "League" role may particpate.
        """
        public_str = "public" if await self._is_public_combine(ctx.guild) else "private"
        response = "Combines are currently **{0}**.".format(public_str)
        await ctx.send(response)

    @commands.command(aliases=["getAcronym"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def acronym(self, ctx):
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
        This is mostly used in #combine-details message
        """
        await self._save_acronym(ctx.guild, new_acronym)
        await ctx.send("The acronym has been registered as **{0}**.".format(new_acronym))

    @commands.Cog.listener("on_voice_state_update")
    async def on_voice_state_update(self, member, before, after):
        combines_ongoing = await self._combines_category(member.guild)

        # ignore when combines are not ongoing, or when voice activity is within the same room
        if not combines_ongoing or before.channel == after.channel:
            return
        
        # Room joined:
        await self._member_joins_voice(member, after.channel)
        # Room left:
        await self._member_leaves_voice(member, before.channel) # TODO: consider disconnected case #@me what does that even mean? this structure should cover everything

    async def _start_combines(self, ctx):
        # Creates combines category and rooms for each tier
        combines_category = await self._add_combines_category(ctx, "Combine Rooms")
        await self._save_combine_category(ctx.guild, combines_category)

        if combines_category:
            await self._add_combines_info_channel(ctx.guild, combines_category, "Combines Details")
            for tier in await self.team_manager_cog.tiers(ctx):
                await self._add_combines_voice(ctx.guild, combines_category, tier)
            return True
        return False

    async def _stop_combines(self, ctx):
        # remove combines channels, category
        combines_category = await self._combines_category(ctx.guild)
        if combines_category:
            for channel in combines_category.channels:
                await channel.delete()
            await combines_category.delete()
            return True
        await ctx.send("could not find combine rooms.")
        return False
    
    async def _update_combine_permissions(self, guild: discord.Guild):
        combines_category = await self._combines_category(guild)
        is_public = await self._is_public_combine(guild)

        if combines_category:
            league_role = self._get_role_by_name(guild, "League")
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=is_public, connect=is_public, send_messages=False),
                league_role: discord.PermissionOverwrite(view_channel=True, connect=True)
            }
            await combines_category.set_permissions(guild.default_role, view_channel=is_public, connect=is_public, send_messages=False)
            await combines_category.set_permissions(league_role, view_channel=True, connect=True, send_messages=False)
    
    async def _add_combines_category(self, ctx, name: str):
        category = await self._combines_category(ctx.guild)
        # check if category exists already
        if category:
            await ctx.send("A category with the name \"{0}\" already exists".format(name))
            return None
        
        if not await self._is_public_combine(ctx.guild):
            league_role = self._get_role_by_name(ctx.guild, "League")
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False, send_messages=False),
                league_role: discord.PermissionOverwrite(view_channel=True, connect=True, send_messages=False)
            }
        else:
            overwrites=None

        category = await ctx.guild.create_category(name, overwrites=overwrites)
        return category

    async def _maybe_remove_combines_voice(self, guild: discord.Guild, voice_channel: discord.VoiceChannel):
        tier = self._get_voice_tier(voice_channel)
        category = await self._combines_category(guild)
        tier_voice_channels = []
        for vc in category.voice_channels:
            if tier in vc.name:
                tier_voice_channels.append(vc)
        
        # Never remove the last room for a tier
        if len(tier_voice_channels) == 1:
            return False

        # Always retain room 1 for tier:
        # await voice_channel.delete()
        i = voice_channel.name.index("room ") + 5
        # DISABLED: active players in room name
        # j = voice_channel.name.index(" (")
        room_num = int(voice_channel.name[i:]) # j])
        room_one_empty = (room_num == 1)

        # if voice_channel was not room 1
        if not room_one_empty:
            # No need to kick scouts. Let them hang out :)
            if voice_channel.members:
                return False
            await voice_channel.delete()
            return True
        
        # delete the other empty room (instead of room 1)
        for vc in tier_voice_channels:
            if not vc.members and vc != voice_channel:
                await vc.delete()
                return True

    async def _add_combines_info_channel(self, guild: discord.Guild, category: discord.CategoryChannel, name: str):
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(send_messages=False)
        }
        tc = await category.create_text_channel(name, position=0, permissions_synced=True, overwrites=overwrites)

        acronym = await self._get_acronym(guild)
        info_message = (
            "Welcome to the {0} combines! Combine rooms will be available to all players who are Free Agents or Draft Eligible. "
            "During combines, you are welcome to spend as much or as little time playing as you'd like. Your participation in combines "
            "gives franchise scouts an opportunity to see how you play. No pressure though! The primary goal for combines is to give "
            "everybody an opportunity to get introduced to gameplay at their respective tiers."

            "\n\n__Server Information__"
            "\nServers can be made by anybody in the combine room. We do ask that the lobbies are made with the following naming convention:"
            "\n\n**Lobby Info:**"
            "\n - Name: **<tier><room number>**"
            "\n - Password: **{1}<room number>**"
            
            "\n\n**Example:**"
            "\n - Voice Channel Name: **Challenger room 4**"
            "\n - Name: **Challenger4**"
            "\n - Password: **{1}4**"

            "\n\n__The Role of Scouts__"
            "\n - For lack of a better phrase, scouts are \"in charge\" of running combines."
            "\n - If a scout requests a lineup, please respect this request."
            "\n - If a scout requests for mutator settings such as adjusted time length, or a goal limit, please respect this request."
            "\n - If you have concerns with how combines are being run, contact a mod or an admin."

            "\n\n__Other Notes__"
            "\n - Please try to curb your particpation in combines towards your own tier. Do not play outside of your tier without being requested "
            "by a scout, or asking permission of the other players in the combine room."
            "\n - Don't stress! All players have good and bad days. Scouts care more about _how you play_ than _how your perform_. If you have a "
            "rough game, or a bad night, you'll have plenty of opportunity to show your abilities in remaining combine games"
            "\n - As per {2} rules, do not be toxic or hostile towards other players."
            "\n - GLHF!"
        ).format(guild.name, acronym.lower(), acronym)
        await tc.send(info_message)
    
    async def _add_combines_voice(self, guild: discord.Guild, category: discord.CategoryChannel, tier: str):
        # user_limit of 0 means there's no limit
        # determine position with same name +1
        tier_rooms = []
        for vc in category.voice_channels:
            if tier in vc.name:
                tier_rooms.append(vc)

        room_makeable = False
        new_position = None
        new_room_number = 1
        while not room_makeable:
            room_makeable = True
            for vc in tier_rooms:
                i = vc.name.index("room ") + 5
                # DISABLED: room count in name
                # j = vc.name.index(" (")
                vc_room_num = int(vc.name[i:])  # j])
                if vc_room_num == new_room_number:
                    new_room_number += 1
                    new_position = vc.position
                    room_makeable = False
        
        # DISABLED: room count in name
        # ppr = await self._players_per_room(guild)
        capacity = await self._room_capacity(guild)
        # room_name = "{0} room {1} (0/{2})".format(tier, new_room_number, ppr)
        room_name = "{0} room {1}".format(tier, new_room_number)

        if not new_position:
            await category.create_voice_channel(room_name, permissions_synced=True, user_limit=capacity)
        else:
            await category.create_voice_channel(room_name, permissions_synced=True, user_limit=capacity, position=new_position)

    async def _member_joins_voice(self, member: discord.Member, voice_channel: discord.VoiceChannel):
        combines_category = await self._combines_category(member.guild)
        if voice_channel in (await self._combines_category(member.guild)).voice_channels:
            player_count = await self._adjust_room_tally(member.guild, voice_channel)
            if player_count == 1:
                tier = self._get_voice_tier(voice_channel)
                await self._add_combines_voice(member.guild, combines_category, tier)
   
    async def _member_leaves_voice(self, member: discord.Member, voice_channel: discord.VoiceChannel):
        if voice_channel in (await self._combines_category(member.guild)).voice_channels:
            # DISABLED
            player_count = await self._adjust_room_tally(member.guild, voice_channel)
            if player_count == 0:
                await self._maybe_remove_combines_voice(member.guild, voice_channel)
        
    async def _get_category_by_name(self, guild: discord.Guild, name: str): 
        for category in guild.categories:
            if category.name == name:
                return category
        return None
    
    # DISABLED :/ (currently only returns player count)
    async def _adjust_room_tally(self, guild: discord.Guild, voice_channel: discord.VoiceChannel):
        # possibility: only call this function when an active player triggers the call and/or make this an increment/decrement function
        fa_role = self._get_role_by_name(guild, "Free Agent")
        de_role = self._get_role_by_name(guild, "Draft Eligible")
        scout_role = self._get_role_by_name(guild, "Combine Scout")
        player_count = 0
        # max_size = await self._players_per_room(guild)
        for member in voice_channel.members:
            if not await self._is_public_combine(guild):
                active_player = (fa_role in member.roles or de_role in member.roles) and scout_role not in member.roles
            else:
                active_player = scout_role not in member.roles
            if active_player:
                    player_count += 1
        
        # DISABLED: channel renaming
        # name_base = voice_channel.name[:voice_channel.name.index(" (")]
        # rename = "{0} ({1}/{2})".format(name_base, player_count, max_size)
        # await voice_channel.edit(name=rename)
        return player_count

    def _get_role_by_name(self, guild: discord.Guild, name: str):
        for role in guild.roles:
            if role.name == name:
                return role
        return None
    
    def _get_voice_tier(self, voice_channel: discord.VoiceChannel):
        return voice_channel.name.split()[0]

    async def _combines_category(self, guild: discord.Guild):
        saved_combine_cat = await self.config.guild(guild).combines_category()
        for category in guild.categories:
            if category.id == saved_combine_cat:
                return category
        return None
    
    async def _save_combine_category(self, guild: discord.Guild, category: discord.CategoryChannel):
        await self.config.guild(guild).combines_category.set(category.id)
    
    # DISABLED: channel renaming
    # async def _players_per_room(self, guild):
    #     ppr = await self.config.guild(guild).players_per_room()
    #     return ppr if ppr else None

    async def _save_players_per_room(self, guild: discord.Guild, num_players: int):
        await self.config.guild(guild).players_per_room.set(num_players)

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

