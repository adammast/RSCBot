from .bulkRoleManager import BulkRoleManager

def setup(bot):
    bot.add_cog(BulkRoleManager(bot))