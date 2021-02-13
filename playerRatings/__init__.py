from .playerRatings import PlayerRatings

def setup(bot):
    bot.add_cog(PlayerRatings(bot))