import discord
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
from collections import Counter


defaults = {}

class RankedRooms(commands.Cog):
    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567892, force_registration=True)
        self.config.register_guild(**defaults)
        self.team_manager_cog = bot.get_cog("teamManager")

    @commands.Cog.listener("on_voice_state_update")
    async def on_voice_state_update(self, member, before, after):
        response_channel = self._get_channel_by_name(member.guild, "tests")
        await response_channel.send("VOICE ACTIVITY DETECTED")

        if before.channel == after.channel:
            return

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def combines(self, ctx, action: str):
        """
        Creates rooms for combines, or tears them down depending on the action parameter
        
        Examples:
        [p]combines start
        [p]combines stop
        """
        if action in ["start", "create"]:
            done = start_combines(ctx)
        elif action in ["stop", "teardown", "end"]
            done = stop_combines(ctx)
        
        if done:
            await ctx.send("Done")
        return
    
    async start_combines(self, ctx):
        return True

    async stop_combines(self, ctx):
        return False

    def _get_channel_by_name(self, guild: discord.guild, name: str):
        for channel in guild.channels:
            if channel.name == name:
                return channel
