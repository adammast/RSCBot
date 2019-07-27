from discord.utils import get
from redbot.core import commands

class AnnoyJK(commands.Cog):
    async def on_message(self, ctx, message):
        if message.author.name == "adammast":
            emoji = get(ctx.guild.emojis(), name='EventElf')
            await message.add_reaction(emoji)