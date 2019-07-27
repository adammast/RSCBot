import discord

from redbot.core import Config
from redbot.core import commands

defaults = {"Users": []}

class Test:
    def __init__(self):
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)

        self.config.register_guild(**defaults)

    @commands.command()
    async def registerUser(self, ctx, user: discord.Member):
        async with self.config.guild(ctx.guild).Users() as users: users.append(user.name.lower())
        await ctx.send(f"{user.name} was added to the word list.")

    @commands.command()
    async def userData(self, ctx):
        data = await self.config.guild(ctx.guild).all()
        await ctx.send(data)