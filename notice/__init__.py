from .notice import Notice

def setup(bot):
    bot.add_cog(Notice(bot))