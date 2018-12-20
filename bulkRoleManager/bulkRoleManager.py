import discord

from discord.ext import commands

class BulkRoleManager:
    """Used to manage roles role for large numbers of members"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True)
    async def getAllWithRole(self, ctx, role : discord.Role, getNickname = False):
        """Prints out a list of members with the specific role"""
        empty = True
        for member in ctx.message.server.members:
            if role in member.roles:
                if getNickname:
                    await self.bot.say("{0.nick}: {0.name}#{0.discriminator}".format(member))
                else:
                    await self.bot.say("{0.name}#{0.discriminator}".format(member))
                empty = False
        if empty:
            await self.bot.say("Nobody has the role {}".format(role.mention))

    @commands.command(pass_context=True)
    async def removeRoleFromAll(self, ctx, role : discord.Role):
        """Removes the role from every member who has it in the server"""
        empty = True
        for member in ctx.message.server.members:
            if role in member.roles:
                await self.bot.remove_roles(member, role)
                empty = False
        if empty:
            await self.bot.say(":x: Nobody has the role {0}".format(role.mention))
        else:
            await self.bot.say(":white_check_mark: Role {0} removed from everyone in the server".format(role.mention))


    @commands.command(pass_context=True)
    async def addRole(self, ctx, role : discord.Role, *userList):
        empty = True
        for user in userList:
            member = await commands.MemberConverter(ctx, user).convert()
            if member in ctx.message.server.members:
                await self.bot.add_roles(member, role)
                empty = False
            else:
                await self.bot.say(":x: Can't find {0}".format(member))
        if empty:
            await self.bot.say(":x: Nobody was given the role {0}".format(role.mention))
        else:
            await self.bot.say(":white_check_mark: Role {0} given to everyone that was found from list".format(role.mention))
            

def setup(bot):
    bot.add_cog(BulkRoleManager(bot))