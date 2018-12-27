import discord
import re

from discord.ext import commands

class Match:
    """Used to get the match information"""

    CONFIG_COG = None

    def __init__(self, bot):
        self.bot = bot
        self.CONFIG_COG = self.bot.get_cog("TransactionConfiguration")

    @commands.command(pass_context=True)
    async def teamList(self, ctx, teamName : str):
        roles = ctx.message.server.roles
        for role in roles:
            if role.name.lower().startswith(teamName.lower()):
                gm = None
                teamMembers = []
                for member in ctx.message.server.members:
                    if role in member.roles:
                        if self.CONFIG_COG.find_role_by_name(member.roles, "General Manager") is not None:
                            gm = member
                        else:
                            teamMembers.append(member)
                message = "```{0}:".format(role.name)
                if gm:
                    if gm.nick:
                        message += "\n{0} (GM".format(gm.nick)
                    else:
                        message += "\n{0} (GM".format(gm.name)
                    if self.CONFIG_COG.find_role_by_name(gm.roles, "Captain") is not None:
                        message += "|C)"
                    else:
                        message += ")"
                for member in teamMembers:
                    message += "\n{0}".format(member.nick)
                    if self.CONFIG_COG.find_role_by_name(member.roles, "Captain") is not None:
                        message += " (C)"
                message += "```"
                await self.bot.say(message)
                return
        await self.bot.say(":x: Could not match {0} to a role".format(teamName))

    @commands.command(pass_context=True)
    async def setMatchDay(self, ctx, day : int):
        """Sets the match day to the specified day. This match day is used when accessing the info in the !match command"""
        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        
        try:
            server_dict.setdefault('Match Day', day)
            self.CONFIG_COG.save_data()
            await self.bot.say("Done")
        except:
            await self.bot.say(":x: Error trying to set the match day. Make sure that the transaction configuration cog is loaded")

    @commands.command(pass_context=True)
    async def getMatchDay(self, ctx):
        """Gets the transaction-log channel"""
        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        
        try:
            day = server_dict["Match Day"]
            await self.bot.say("Match day set to: {0}".format(day))
        except:
            await self.bot.say(":x: Match day not set")

def setup(bot):
    bot.add_cog(Match(bot))