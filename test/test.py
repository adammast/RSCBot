import discord
from discord.ext import commands

class Test:
    """My custom cog that does stuff!"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def mycom(self):
        """This does stuff!"""

        #Your code will go here
        await self.bot.say("I can do stuff!")

    @commands.command()
    async def punch(self, user : discord.Member):
        """I will punch anyone! >.<"""

        await self.bot.say("ONE PUNCH! And " + user.mention + " is out! ლ(ಠ益ಠლ)")

    @bot.command(pass_context=True)
    @commands.command()
    async def draft(self, user : discord.Member, teamRole : discord.Role):
        self.bot.add_roles(user, teamRole)
        await self.bot.say(user.mention + " was drafted onto the " + teamRole.name)

def setup(bot):
    bot.add_cog(Test(bot))