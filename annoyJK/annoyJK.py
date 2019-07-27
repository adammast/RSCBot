from discord.utils import get

class AnnoyJK():
    async def on_message(self, message):
        if message.author.name == "adammast":
            emoji = get(guild.emojis(), name='EventElf')
            await message.add_reaction(emoji)