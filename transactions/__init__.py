from .transactions import Transactions

def setup(bot):
    bot.add_cog(Transactions(bot))