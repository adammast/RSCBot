from discord.ext import commands

class AnnoyJK:

    JK_ID = 226869393626234881

    def __init__(self, bot):
        self.bot = bot

    async def on_message(self, message):
        if message.author.id == self.JK_ID:
            await self.bot.add_reaction(message, '👍')

def setup(bot):
    bot.add_cog(AnnoyJK(bot))