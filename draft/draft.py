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
        """Assigns the team role to a user when they are drafted and posts to the assigned channel"""
        server = ctx.message.server
        server_dict = self.config.setdefault(server.id, {})
        
        try:
            channelId = server_dict['Transaction Channel']
        except KeyError:
            await self.bot.say(":x: Transaction log channel not set")
        else:
            try:
                roleId = server_dict['League Role']
            except KeyError:
                await self.bot.say(":x: League role not currently set")
            else:
                channel = server.get_channel(channelId)
                role = server.get_role(roleId)
                message = "{0} was drafted by the {1}".format(user.mention, teamRole.mention)
                await self.bot.add_roles(user, teamRole)
                await self.bot.add_roles(user, role)
                await self.bot.send_message(channel, message)          

    @commands.command(pass_context=True)
    async def setTransactionLogChannel(self, ctx, tlog : discord.Channel):
        """Assigns the specified channel as the channel where all transactions will be announced"""
        server = ctx.message.server
        server_dict = self.config.setdefault(server.id, {})

        try:
            server_dict.setdefault('Transaction Channel', tlog.id)
            self.save_data()
            await self.bot.say(":white_check_mark: Transaction log channel now set to {0}".format(tlog.mention))
        except:
            await self.bot.say(":x: Error setting transaction log channel to {0}".format(tlog.mention))

    @commands.command(pass_context=True)
    async def getTransactionLogChannel(self, ctx):
        """Gets the transaction-log channel"""
        server = ctx.message.server
        server_dict = self.config.setdefault(server.id, {})
        
        try:
            channelId = server_dict['Transaction Channel']
        except KeyError:
            await self.bot.say(":x: Transaction log channel not currently set")
        else:
             channel = server.get_channel(channelId)
             await self.bot.say("Transaction log channel currently set to {0}".format(channel.mention))

    @commands.command(pass_context=True)
    async def unsetTransactionLogChannel(self, ctx):
        """Unassignes the transaction-log channel"""
        server = ctx.message.server
        server_dict = self.config.setdefault(server.id, {})

        channelId = server_dict.pop('Transaction Channel', None)
        if channelId:
            channel = server.get_channel(channelId)
            await self.bot.say(":white_check_mark: Transaction log channel no longer set to {0}".format(channel.mention))
        else:
            await self.bot.say(":x: Transaction log channel has not been set")

    @commands.command(pass_context=True)
    async def setLeagueRole(self, ctx, leagueRole : discord.Role):
        """Assigns the specified role as the "League" role so it can be given to all the players that are drafted"""
        server = ctx.message.server
        server_dict = self.config.setdefault(server.id, {})

        try:
            server_dict.setdefault('League Role', leagueRole.id)
            self.save_data()
            await self.bot.say(":white_check_mark: League role now set to {0}".format(leagueRole.name))
        except:
            await self.bot.say(":x: Error setting league role to {0}".format(leagueRole.name))

    @commands.command(pass_context=True)
    async def getLeagueRole(self, ctx):
        """Gets the transaction-log channel"""
        server = ctx.message.server
        server_dict = self.config.setdefault(server.id, {})
        
        try:
            roleId = server_dict['League Role']
        except KeyError:
            await self.bot.say(":x: League role not currently set")
        else:
             role = server.get_role(roleId)
             await self.bot.say("League role currently set to {0}".format(role.name))

    @commands.command(pass_context=True)
    async def unsetLeagueRole(self, ctx):
        """Unassignes the transaction-log channel"""
        server = ctx.message.server
        server_dict = self.config.setdefault(server.id, {})

        roleId = server_dict.pop('League Role', None)
        if roleId:
            channel = server.get_channel(channelId)
            await self.bot.say(":white_check_mark: League role no longer set to {0}".format(role.name))
        else:
            await self.bot.say(":x: League role has not been set")

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