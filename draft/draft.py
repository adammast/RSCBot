import discord
import os.path
import os

from .utils.dataIO import dataIO
from discord.ext import commands
from cogs.utils import checks

class Draft:
    """Used to draft players onto teams and give the the appropriate roles"""

    DATA_FOLDER = "data/draft"
    CONFIG_FILE_PATH = DATA_FOLDER + "/config.json"

    CONFIG_DEFAULT = {}

    def __init__(self, bot):
        self.bot = bot
        self.check_configs()
        self.load_data()

    @commands.command(pass_context=True)
    async def draft(self, ctx, user : discord.Member, teamRole : discord.Role):
        server = ctx.message.server
        server_dict = self.config.setdefault(server.id, {})
        channelId = server_dict['Transaction Channel']

        if channelId:
            channel = server.get_channel(channelId)
            message = "{0} was drafted onto the {1}".format(user.mention, teamRole.mention)
            await self.bot.add_roles(user, teamRole)
            await self.bot.send_message(channel, message)
        else:
            await self.bot.say(":X: Transaction log channel not set")

    @commands.command(pass_context=True)
    async def setTransactionLogChannel(self, ctx, tlog : discord.Channel):
        """Sets the transaction-log channel"""
        server = ctx.message.server
        server_dict = self.config.setdefault(server.id, {})

        server_dict.setdefault('Transaction Channel', tlog.id)
        self.save_data()
        await self.bot.say("Transaction Log channel set to " + tlog.mention)

    @commands.command(pass_context=True)
    async def getTransactionLogChannel(self, ctx):
        """Gets the transaction-log channel"""
        server = ctx.message.server
        server_dict = self.config.setdefault(server.id, {})
        channelId = server_dict['Transaction Channel']

        if channelId:
            channel = server.get_channel(channelId)
            await self.bot.say("Transaction log channel set to {0}".format(channel.mention))
        else:
            await self.bot.say(":X: Transaction log channel not set")

    @commands.command(pass_context=True)
    async def removeTransactionLogChannel(self, ctx):
        """Removes the transaction-log channel"""
        server = ctx.message.server
        server_dict = self.config.setdefault(server.id, {})

        channelId = server_dict.pop('Transaction Channel', None)
        if channelId:
            channel = server.get_channel(channelId)
            await self.bot.say("Transaction log channel no longer set to {0}".format(channel.mention))
        else:
            await self.bot.say(":X: Transaction log channel was not set")

    # Config
    def check_configs(self):
        self.check_folders()
        self.check_files()

    def check_folders(self):
        if not os.path.exists(self.DATA_FOLDER):
            os.makedirs(self.DATA_FOLDER, exist_ok=True)

    def check_files(self):
        self.check_file(self.CONFIG_FILE_PATH, self.CONFIG_DEFAULT)

    def check_file(self, file, default):
        if not dataIO.is_valid_json(file):
            dataIO.save_json(file, default)

    def load_data(self):
        self.config = dataIO.load_json(self.CONFIG_FILE_PATH)

    def save_data(self):
        dataIO.save_json(self.CONFIG_FILE_PATH, self.config)

def setup(bot):
    bot.add_cog(Draft(bot))