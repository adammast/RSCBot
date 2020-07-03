import discord
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
from collections import Counter


defaults = {"room_size": 4, "combines_category": None}

# TODO list:
#   - team_manager_cog
#   - set/save/update combine details (i.e. room size, combines category while active)
#   - room permissions ("League" role, GM, AGM, scout, mod, or admins may join)
#   - listener behavior
#       - player join
#           - maybe make new/move room (A: move player to new room, B: add 2nd room, move original)    
#           - increase room size (x/4)
#       - player leave
#           - maybe remove room
#           - decrement room size (x/4)

class RankedRooms(commands.Cog):
    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567892, force_registration=True)
        self.config.register_guild(**defaults)
        self.team_manager_cog = bot.get_cog("teamManager")
        self.combines_category_name = "Combine Rooms"

    @commands.Cog.listener("on_voice_state_update")
    async def on_voice_state_update(self, member, before, after):
        response_channel = self._get_channel_by_name(member.guild, "tests")
        await response_channel.send("VOICE ACTIVITY DETECTED")

        if before.channel == after.channel:
            return

    @commands.command(aliases=["startcombines", "stopcombines"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def combines(self, ctx, action=None):
        """
        Creates rooms for combines, or tears them down depending on the action parameter
        
        Examples:
        [p]combines start
        [p]combines stop
        """
        if action in ["start", "create"]:
            done = await self._start_combines(ctx)
        elif action in ["stop", "teardown", "end"]:
            done = await self._stop_combines(ctx)
        else:
            done = await self._start_combines(ctx) # TODO: make parameter optional, should behave as a switch.
        
        if done:
            await ctx.send("Done")
        return
    
    async def _start_combines(self, ctx):
        # check if combines are running already (maybe check config file)
        # create combines category
        combines_category = await self._add_category(ctx, self.combines_category_name)
        # create DYNAMIC ROOMS for each rank
        if combines_category:
            for tier in ["Minor", "Major"]:  # self.team_manager_cog.tiers(ctx): # TODO: Make sure this cog works
                await self.add_combines_voice(combines_category, tier)
                # name: <tier> combines: Octane (identifier?)
                # permissions:
                    # <tier> voice visible by <tier, admin, mod, GM, AGM, scout>
                # behavior: 
                    # (listener command) => if 5th joins room, send to waiting room/new room?
                    # allow 4 PLAYERS, but allow x scouts/GMs
            return True
        return False

    async def _stop_combines(self, ctx):
        # remove combines channels, category
        combines_category = await self._get_category_by_name(ctx.guild, self.combines_category_name)
        if combines_category:
            for channel in combines_category.channels:
                await channel.delete()
            await combines_category.delete()
            return True
        await ctx.send("Could not find combine rooms.")
        return False

    def _get_channel_by_name(self, guild: discord.guild, name: str):
        for channel in guild.channels:
            if channel.name == name:
                return channel
    
    async def _add_category(self, ctx, name: str):
        category = await self._get_category_by_name(ctx.guild, name)
        if category:
            await ctx.send("A category with the name \"{0}\" already exists".format(name))
            return None
        category = await ctx.guild.create_category(name)
        return category

    async def add_combines_voice(self, category: discord.CategoryChannel, tier: str):
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
                i = vc.name.index("room ")
                j = vc.name.index(" (")
                vc_room_num = int(vc.name[i:j])
                if vc_room_num == new_room_number:
                    new_room_number += 1
                    new_position = vc.position + 1
                    room_makeable = False
        
        room_name = "{0} room {1} (0/4)".format(tier, new_room_number)
        if not new_position:
            await category.create_voice_channel(room_name)
        else:
            await category.create_voice_channel(room_name, position=new_position)

    async def _get_category_by_name(self, guild: discord.guild, name: str):
        for category in guild.categories:
            if category.name == name:
                return category
        return None
        
