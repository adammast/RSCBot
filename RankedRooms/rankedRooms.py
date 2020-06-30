import discord


from redbot.core import Config
from redbot.core import commands
from redbot.core import checks


defaults = {}

class RankedRooms(commands.Cog):
    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567892, force_registration=True)
        self.config.register_guild(**defaults)

    # @client.event
    @commands.Cog.listener()
    async def on_voice_update(member, before, after):
        test_text_id = 512343431213875203
        # channel = get(server.channels, name=name, type=discord.ChannelType.text)
        await self.getTestChannel().send("VOICE CHANNEL ACTIVATED")


    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setTestChannel(self, ctx, trans_channel: discord.TextChannel):
        """Sets the channel where all test reponse messages will be posted"""
        await self._save_test_channel(ctx, trans_channel.id)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command(aliases=["getTransChannel"])
    @checks.admin_or_permissions(manage_guild=True)
    async def getTestChannel(self, ctx):
        """Gets the channel currently assigned test response channel"""
        try:
            await ctx.send("Test log channel set to: {0}".format((await self._trans_channel(ctx)).mention))
        except:
            await ctx.send(":x: Test log channel not set")

    @commands.guild_only()
    @commands.command(aliases=["unsetTransChannel"])
    @checks.admin_or_permissions(manage_guild=True)
    async def unsetTestChannel(self, ctx):
        """Unsets the test response channel. Transactions will not be performed if no transaction channel is set"""
        await self._save_test_channel(ctx, None)
        await ctx.send("Done")

    async def _save_test_channel(self, ctx, trans_channel):
        await self.config.guild(ctx.guild).TestChannel.set(test_channel)
    