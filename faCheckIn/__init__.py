from .faCheckIn import FaCheckIn

def setup(bot):
    bot.add_cog(FaCheckIn(bot))