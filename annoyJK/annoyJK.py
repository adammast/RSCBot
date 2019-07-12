from discord.utils import get

class AnnoyJK:

    def __init__(self, bot):
        self.bot = bot

    async def on_message(self, message):
        if message.author.name == "adammast":
            emoji = get(self.bot.get_all_emojis(), name='EventElf')
            await self.bot.add_reaction(message, emoji)

def setup(bot):
    n = AnnoyJK(bot)
    bot.add_listener(n.on_message, "on_message")
    bot.add_cog(n)