import discord
import os.path
import os

from .utils.dataIO import dataIO
from discord.ext import commands
from cogs.utils import checks

class Draft:
    """Used to draft players onto teams and give the the appropriate roles"""

    DATA_FOLDER = "data/transactionConfiguration"
    CONFIG_FILE_PATH = DATA_FOLDER + "/config.json"

    CONFIG_DEFAULT = {}

    def __init__(self, bot):
        self.bot = bot
        self.check_configs()
        self.load_data()

    @commands.command(pass_context=True)
    async def pop(self, ctx):
        server = ctx.message.server
        server_dict = self.config.setdefault(server.id, {})
        try:
            await self.bot.say("Next item in dictionary {0}".format(server_dict.pop()))
        except:
            await self.bot.say("Something went wrong, I'm a dumb bot with a poop butt")

    @commands.command(pass_context=True)
    async def draft(self, ctx, user : discord.Member, teamRole : discord.Role):
        """Assigns the team role and league role to a user when they are drafted and posts to the assigned channel"""
        server = ctx.message.server
        server_dict = self.config.setdefault(server.id, {})
        
        try:
            channelId = server_dict['Transaction Channel']
        except KeyError:
            await self.bot.say(":x: Transaction log channel not set")
        else:
            try:
                leagueRoleId = server_dict['League Role']
            except KeyError:
                await self.bot.say(":x: League role not currently set")
            else:
                try:
                    leagueRole = self.find_role(server.roles, leagueRoleId)
                except LookupError:
                    await self.bot.say(":x: Could not find role with id of {0}".format(leagueRoleId))
                else:
                    channel = server.get_channel(channelId)
                    message = "{0} was drafted by the {1}".format(user.mention, teamRole.mention)
                    await self.bot.add_roles(user, teamRole)
                    await self.bot.add_roles(user, leagueRole)
                    await self.bot.send_message(channel, message)       

    def find_role(self, roles, roleId):
        for role in roles:
            if role.id == roleId:
                return role
        raise LookupError('roleId not found in server roles')

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