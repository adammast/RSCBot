import discord

from redbot.core import commands
from redbot.core import checks
from redbot.core import Config

defaults = {"DefaultChannel": None}

class Notice(commands.Cog):
    """Used to send a notice to a specified channel and ping a specified role"""

    def __init__(self):
        self.config = Config.get_conf(self, identifier=1234567897, force_registration=True)
        self.config.register_guild(**defaults)

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def notice(self, ctx, message, *, pingRole: discord.Role, channel: discord.TextChannel = None):
        """Sends a notice to a specified channel and pings the specified role(s)
        
        Arguments:
            message -- The message to be posted. Must have quotes around it if it's more than one word
            pingRole -- Can be 1 or more roles that you want to ping in the notice
            channel -- Can be 0 or 1 channel where the notice will be posted. If no channel is given it will try and post to the default notice channel

        Notice will be in this format:
            @role(s)
            
            [message]"""
        
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setNoticeChannel(self, ctx, default_channel: discord.TextChannel):
        """Sets the default notice channel where notices will be sent unless another channel is specified"""
        await self._save_default_channel(ctx, default_channel.id)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def getNoticeChannel(self, ctx):
        """Gets the default notice channel where notices will be sent unless another channel is specified"""
        try:
            await ctx.send("Default notice channel set to: {0}".format((await self._default_channel(ctx)).mention))
        except:
            await ctx.send(":x: Default notice channel not set")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def unsetNoticeChannel(self, ctx):
        """Unsets the default notice channel where notices will be sent unless another channel is specified"""
        await self._save_default_channel(ctx, None)
        await ctx.send("Done")

    async def _default_channel(self, ctx):
        return ctx.guild.get_channel(await self.config.guild(ctx.guild).DefaultChannel())

    async def _save_default_channel(self, ctx, channel):
        await self.config.guild(ctx.guild).DefaultChannel.set(channel)