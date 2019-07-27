import discord

from redbot.core import Config
from redbot.core import commands

defaults = {"Users": {}}

class Test(commands.Cog):
    def __init__(self):
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)

        self.config.register_guild(**defaults)

    @commands.command()
    async def registerUser(self, ctx, user: discord.Member):
        async with self.config.guild(ctx.guild).Users() as users:
            users[user.id] = user.name
        await ctx.send(f"{user.name} was added to the word list.")

    @commands.command()
    async def getUserName(self, ctx, id):
        users = await self.config.guild(ctx.guild).Users()
        username = users[id]
        await ctx.send("Name = {0}".format(username))

    @commands.command()
    async def userData(self, ctx):
        data = await self.config.guild(ctx.guild).all()
        await ctx.send(data)

    @commands.command()
    async def clearData(self, ctx):
        await self.config.guild(ctx.guild).Users.clear()
        await ctx.send("User data was cleared.")

    @commands.command()
    async def addTestData(self, ctx):
        await self.config.guild(ctx.guild).Users.set({226869393626234881: "adammast", 137652497178296320: "cakekyst"})
        await ctx.send("Data set to test data.")