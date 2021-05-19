
from .config import config
from .bcManager import BCManager

def setup(bot):
    bot.add_cog(BCManager(bot))