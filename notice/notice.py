import discord

from redbot.core import commands
from redbot.core import checks
from redbot.core import Config
from redbot.core.utils.predicates import MessagePredicate

defaults = {"NoticeChannel": None}

class Notice(commands.Cog):
    """Used to send a notice to a specified channel and ping the specified role(s)"""

    def __init__(self):
        self.config = Config.get_conf(self, identifier=1234567897, force_registration=True)
        self.config.register_guild(**defaults)

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def notice(self, ctx, message, *pingRole: discord.Role):
        """Sends a notice to the channel set using the *setNoticeChannel* command and pings the specified role(s)
        
        Arguments:
            message -- The message to be posted. Must have quotes around it if it's more than one word
            pingRole -- Can be 1 or more roles that you want to ping in the notice

        Notice will be in this format:
            @role(s)
            
            [message]"""

        await ctx.send("Which channel do you want to send the notice too?\nUse `{}cancel` to cancel the command".format(ctx.prefix))
        pred = MessagePredicate.valid_text_channel(ctx)
        await ctx.bot.wait_for("message", check=pred)
        channel = pred.result
        
        await ctx.send("{}".format(channel.mention))

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setNoticeChannel(self, ctx, default_channel: discord.TextChannel):
        """Sets the notice channel where notices will be sent unless another channel is specified"""
        await self._save_default_channel(ctx, default_channel.id)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def getNoticeChannel(self, ctx):
        """Gets the notice channel where notices will be sent unless another channel is specified"""
        try:
            await ctx.send("Default notice channel set to: {0}".format((await self._default_channel(ctx)).mention))
        except:
            await ctx.send(":x: Default notice channel not set")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def unsetNoticeChannel(self, ctx):
        """Unsets the notice channel where notices will be sent unless another channel is specified"""
        await self._save_default_channel(ctx, None)
        await ctx.send("Done")

    async def _notice_channel(self, ctx):
        return ctx.guild.get_channel(await self.config.guild(ctx.guild).NoticeChannel())

    async def _save_notice_channel(self, ctx, channel):
        await self.config.guild(ctx.guild).NoticeChannel.set(channel)