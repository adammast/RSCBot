import discord
import csv
import os

from redbot.core import commands
from redbot.core import checks
from discord import File

class BulkRoleManager(commands.Cog):
    """Used to manage roles role for large numbers of members"""

    @commands.command()
    @commands.guild_only()
    async def getAllWithRole(self, ctx, role: discord.Role, getNickname = False):
        """Prints out a list of members with the specific role"""
        count = 0
        messages = []
        message = ""
        await ctx.send("Players with {0} role:\n".format(role.name))
        for member in ctx.guild.members:
            if role in member.roles:
                if getNickname:
                    message += "{0.nick}: {0.name}#{0.discriminator}\n".format(member)
                else:
                    message += "{0.name}#{0.discriminator}\n".format(member)
                if len(message) > 1900:
                    messages.append(message)
                    message = ""
                count += 1
        if count == 0:
            await ctx.send("Nobody has the {0} role".format(role.name))
        else:
            if message is not "":
                messages.append(message)
            for msg in messages:
                await ctx.send("{0}{1}{0}".format("```", msg))
            await ctx.send(":white_check_mark: {0} player(s) have the {1} role".format(count, role.name))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def removeRoleFromAll(self, ctx, role: discord.Role):
        """Removes the role from every member who has it in the server"""
        empty = True
        for member in ctx.message.guild.members:
            if role in member.roles:
                await member.remove_roles(role)
                empty = False
        if empty:
            await ctx.send(":x: Nobody has the {0} role".format(role.mention))
        else:
            await ctx.send(":white_check_mark: {0} role removed from everyone in the server".format(role.name))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def addRole(self, ctx, role : discord.Role, *userList):
        """Adds the role to every member that can be found from the userList"""
        empty = True
        added = 0
        had = 0
        notFound = 0
        message = ""
        for user in userList:
            try:
                member = await commands.MemberConverter().convert(ctx, user)
                if member in ctx.guild.members:
                    if role not in member.roles:
                        await member.add_roles(role)
                        added += 1
                    else:
                        had += 1
                    empty = False
            except:
                if notFound == 0:
                    message += "Couldn't find:\n"
                message += "{0}\n".format(user)
                notFound += 1
        if empty:
            message += ":x: Nobody was given the role {0}".format(role.name)
        else:
           message += ":white_check_mark: {0} role given to everyone that was found from list".format(role.name)
        if notFound > 0:
            message += ". {0} user(s) were not found".format(notFound)
        if had > 0:
            message += ". {0} user(s) already had the role".format(had)
        if added > 0:
            message += ". {0} user(s) had the role added to them".format(added)
        await ctx.send(message)

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def makeDE(self, ctx, *userList):
        """Adds the Draft Eligible and League roles, removes Spectator role, and adds the DE prefix to every member that can be found from the userList"""
        empty = True
        added = 0
        had = 0
        notFound = 0
        deRole = None
        leagueRole = None
        spectatorRole = None
        message = ""
        for role in ctx.guild.roles:
            if role.name == "Draft Eligible":
                deRole = role
            elif role.name == "League":
                leagueRole = role
            elif role.name == "Spectator":
                spectatorRole = role
            if leagueRole and deRole and spectatorRole:
                break

        if deRole is None or leagueRole is None or spectatorRole is None:
            await ctx.send("Couldn't find either the Draft Eligible, League, or Spectator role in the server")
            return

        for user in userList:
            try:
                member = await commands.MemberConverter().convert(ctx, user)
                if member in ctx.guild.members:
                    if leagueRole not in member.roles:
                        await member.add_roles(deRole, leagueRole)
                        added += 1
                        await member.edit(nick="{0} | {1}".format("DE", self.get_player_nickname(member)))
                        await member.remove_roles(spectatorRole)
                    else:
                        message += "Already in League: {0}\n".format(member.mention)
                        had += 1
                    empty = False
            except:
                message += "Couldn't find: {0}\n".format(user)
                notFound += 1
        if empty:
            message += ":x: Nobody was given the Draft Eligible role"
        else:
           message += ":white_check_mark: Draft Eligible role given to everyone that was found from list"
        if notFound > 0:
            message += ". {0} user(s) were not found".format(notFound)
        if had > 0:
            message += ". {0} user(s) already had the role or were already in the league".format(had)
        if added > 0:
            message += ". {0} user(s) had the role added to them".format(added)
        await ctx.send(message)
    
    @commands.command()
    @commands.guild_only()
    async def getId(self, ctx, *userList):
        """Gets the id for any user that can be found from the userList"""
        notFound = []
        messages = []
        message = ""
        for user in userList:
            try:
                member = await commands.MemberConverter().convert(ctx, user)
                if member in ctx.guild.members:
                    nickname = self.get_player_nickname(member)
                    message += "{1}:{0.name}#{0.discriminator}:{0.id}\n".format(member, nickname)
                if len(message) > 1900:
                    messages.append(message)
                    message = ""
            except:
                notFound.append(user)
        if len(notFound) > 0:
            notFoundMessage = ":x: Couldn't find:\n"
            for user in notFound:
                notFoundMessage += "{0}\n".format(user)
            await ctx.send(notFoundMessage)
        if message is not "":
            messages.append(message)
        for msg in messages:
            await ctx.send("{0}{1}{0}".format("```", msg))

    @commands.command()
    @commands.guild_only()
    async def getIdsWithRole(self, ctx, role: discord.Role, spreadsheet: bool = False):
        """Gets the id for any user that has the given role"""
        messages = []
        message = ""
        if spreadsheet:
            Outputcsv = "Ids.csv"
            header = ["Nickname","Name","Id"]
            csvwrite = open(Outputcsv, 'w', newline='')
            w = csv.writer(csvwrite, delimiter=',')
            w.writerow(header)
            for member in ctx.guild.members:
                if role in member.roles:
                    nickname = self.get_player_nickname(member)
                    newrow = ["{0}".format(nickname), "{0.name}#{0.discriminator}".format(member), "{0.id}".format(member)]
                    w.writerow(newrow)
            csvwrite.close()
            await ctx.send("Done", file=File(Outputcsv))
            os.remove(Outputcsv)
        else:
            for member in ctx.guild.members:
                if role in member.roles:
                    nickname = self.get_player_nickname(member)
                    message += "{1}:{0.name}#{0.discriminator}:{0.id}\n".format(member, nickname)
                    if len(message) > 1900:
                        messages.append(message)
                        message = ""
            if message is not "":
                messages.append(message)
            for msg in messages:
                await ctx.send("{0}{1}{0}".format("```", msg))
        

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def giveRoleToAllWithRole(self, ctx, currentRole: discord.Role, roleToGive: discord.Role):
        """Gives the roleToGive to every member who already has the currentRole"""
        count = 0
        hadRoleCount = 0
        countGiven = 0
        
        for member in ctx.guild.members:
            if currentRole in member.roles:
                count += 1
                if roleToGive in member.roles:
                    hadRoleCount += 1
                else:
                    await member.add_roles(roleToGive)
                    countGiven += 1
        if count == 0:
            message = ":x: Nobody has the {0} role".format(currentRole.name)
        else:
            message = ":white_check_mark: {0} user(s) had the {1} role".format(count, currentRole.name)
            if hadRoleCount > 0:
                message += ". {0} user(s) already had the {1} role".format(hadRoleCount, roleToGive.name)
            if countGiven > 0:
                message += ". {0} user(s) had the {1} role added to them".format(countGiven, roleToGive.name)
        await ctx.send(message)

    def get_player_nickname(self, user: discord.Member):
        if user.nick is not None:
            array = user.nick.split(' | ', 1)
            if len(array) == 2:
                currentNickname = array[1].strip()
            else:
                currentNickname = array[0]
            return currentNickname
        return user.name