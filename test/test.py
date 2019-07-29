from redbot.core import commands


class Testcog(commands.Cog):
    """Documentation is hard."""

    @commands.command()
    async def testcommand(self, ctx):
        """This does stuff!"""
        # Your code will go here
        await ctx.send("Shutup")