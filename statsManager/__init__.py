from .statsManager import StatsManager

def setup(bot):
    bot.add_cog(StatsManager(bot))