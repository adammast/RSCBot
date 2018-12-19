import discord
import os.path
import os

from .utils.dataIO import dataIO
from discord.ext import commands
from cogs.utils import checks

class PrefixManager:
    """Used to set team and role prefixes and give to members on those teams or with those roles"""

    DATA_FOLDER = "data/transactionConfiguration"
    CONFIG_FILE_PATH = DATA_FOLDER + "/config.json"

    CONFIG_DEFAULT = {}

    @commands.command(pass_context=True)
    async def arrayTest(self, ctx, **keyValuePair):
        for key, value in keyValuePair.items():
            await self.bot.say("Prefix for {0} = {1}".format(key, value))

    def find_role(self, roles, roleId):
        for role in roles:
            if role.id == roleId:
                return role
        raise LookupError('roleId not found in server roles')

    def __init__(self, bot):
        self.bot = bot
        self.check_configs()
        self.load_data()

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
    bot.add_cog(PrefixManager(bot))