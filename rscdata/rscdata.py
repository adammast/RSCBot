import os.path
import os
import json
import logging

from .utils.dataIO import dataIO
from discord.ext import commands
from cogs.utils import checks


class RscData:
    """Utility cog for storing and retrieving data.

    Currently just writes JSON to files. Could be changed to another file
    format or, in theory, to use an actual database.
    """
    DATA_FOLDER = "data/rscdata"
    LOG_FILE = DATA_FOLDER + "/rsc.log"

    DATA_BOOTSTRAP = {}
    SERVERLESS = "no_server"

    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True)
    @checks.admin_or_permissions(manage_server=True)
    async def dumpDataset(self, ctx, dataset):
        json_dump = json.dumps(
            self.load(ctx, dataset), indent=4, sort_keys=True)
        await self.bot.say("Dataset: {0}\n{1}".format(dataset, json_dump))

    def load(self, ctx, dataset):
        """Return the data for the named dataset in the server from the
        supplied context."""
        return self._load_data(ctx, dataset)

    def save(self, ctx, dataset, data):
        """Save the provided data into the named dataset in the server
        for the provided context.

        The current implementation completely overwrites the specified
        dataset.
        """
        self._save_data(ctx, dataset, data)

    def logger(self):
        return logger

    def _dataset_file(self, dataset):
        return "{0}/{1}.json".format(self.DATA_FOLDER, dataset)

    def _ensure_dataset_file(self, dataset):
        """Create the specified file if it does not exist."""
        dataset_file = self._dataset_file(dataset)
        if not dataIO.is_valid_json(dataset_file):
            dataIO.save_json(dataset_file, self.DATA_BOOTSTRAP)

    def _server_set_for(self, ctx):
        """Return the name of the dict to be used for the server in the
        provided context."""
        if ctx.message.server:
            return str(ctx.message.server.id)
        else:
            return self.SERVERLESS

    def _load_data(self, ctx, dataset):
        """Load the data dictionary from the file."""
        all_data = self._all_data(dataset)
        server_set = self._server_set_for(ctx)
        data = all_data.setdefault(server_set, self.DATA_BOOTSTRAP)
        return data

    def _save_data(self, ctx, dataset, data):
        """Save the data into the dataset within the context provided.

        This overwrites any pre-existing data.
        """
        server_set = self._server_set_for(ctx)
        all_data = self._all_data(dataset)
        all_data[server_set] = data
        dataIO.save_json(self._dataset_file(dataset), all_data)

    def _all_data(self, dataset):
        self._ensure_dataset_file(dataset)
        return dataIO.load_json(self._dataset_file(dataset))


def ensure_data_folder():
    """Create the needed data folder if it does not exist."""
    if not os.path.exists(RscData.DATA_FOLDER):
        os.makedirs(RscData.DATA_FOLDER, exist_ok=True)


def setup(bot):
    global logger
    ensure_data_folder()
    logger = logging.getLogger("rsc.data")
    if logger.level == 0:
        # Prevents the logger from being loaded again in case of module reload
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(
            filename=RscData.LOG_FILE, encoding='utf-8', mode='a')
        handler.setFormatter(logging.Formatter(
            '%(asctime)s %(message)s', datefmt="[%d/%m/%Y %H:%M]"))
        logger.addHandler(handler)
    bot.add_cog(RscData(bot))
