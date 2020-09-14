from .streamSignupManager import StreamSignupManager

def setup(bot):
    bot.add_cog(StreamSignupManager(bot))