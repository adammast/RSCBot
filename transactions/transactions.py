import discord
import os.path
import os
import re

from .utils.dataIO import dataIO
from discord.ext import commands
from cogs.utils import checks

class Transactions:
    """Used to set franchise and role prefixes and give to members in those franchises or with those roles"""

    DATA_FOLDER = "data/transactionConfiguration"
    CONFIG_FILE_PATH = DATA_FOLDER + "/config.json"

    CONFIG_DEFAULT = {}

    def __init__(self, bot):
        self.bot = bot
        self.check_configs()
        self.load_data()

    @commands.command(pass_context=True)
    async def sign(self, ctx, user : discord.Member, teamRole : discord.Role):
        """Assigns the team role, franchise role and prefix to a user when they are signed and posts to the assigned channel"""
        if teamRole in user.roles:
            await self.bot.say(":x: {0} is already on the {1}".format(user.mention, teamRole.mention))
            return
        
        server_dict = self.get_server_dict(ctx)

        channel = self.get_transaction_channel(server_dict)
        if channel is not None:
            leagueRole = self.get_league_role(server_dict, ctx.message.server)
            if leagueRole is not None:
                franchiseRole = self.get_franchise_role(server_dict, ctx.message.server, teamRole)
                if franchiseRole is not None:
                    prefix = self.get_prefix(server_dict, teamRole)
                    if prefix is not None:
                        message = "{0} was signed by the {1}".format(user.mention, teamRole.mention)
                        freeAgentRole = self.find_role(ctx.message.server.roles, server_dict['Free Agent'])
                        if freeAgentRole in user.roles:
                            await self.bot.remove_roles(user, freeAgentRole)
                        await self.bot.change_nickname(user, "{0} | {1}".format(prefix, user.name))
                        await self.bot.add_roles(user, teamRole, leagueRole, franchiseRole)
                        await self.bot.send_message(channel, message)

    @commands.command(pass_context=True)
    async def cut(self, ctx, user : discord.Member, teamRole : discord.Role):
        """Removes the team role and franchise role, and adds the free agent prefix to a user and posts to the assigned channel"""
        if teamRole not in user.roles:
            await self.bot.say(":x: {0} is not on the {1}".format(user.mention, teamRole.mention))
            return

        server_dict = self.get_server_dict(ctx)

        channel = self.get_transaction_channel(server_dict)
        if channel is not None:
            franchiseRole = self.get_franchise_role(server_dict, ctx.message.server, teamRole)
            if franchiseRole is not None:
                prefix = self.get_prefix(server_dict, teamRole)
                if prefix is not None:
                    await self.bot.remove_roles(user, teamRole, franchiseRole)
                    await self.bot.change_nickname(user, "FA | {0}".format(user.name))
                    freeAgentRole = self.find_role(ctx.message.server.roles, server_dict['Free Agent'])
                    await self.bot.add_roles(user, freeAgentRole)
                    message = "{0} was cut by the {1}. He will now be on waivers".format(user.mention, teamRole.mention)
                    await self.bot.send_message(channel, message)


    @commands.command(pass_context=True)
    async def trade(self, ctx, user : discord.Member, newTeamRole : discord.Role, user2 : discord.Member, newTeamRole2 : discord.Role):
        """Swaps the teams of the two players and announces the trade in the assigned channel"""
        if newTeamRole2 not in user.roles:
            await self.bot.say(":x: {0} is not on the {1}".format(user.mention, newTeamRole2.mention))
            return
        elif newTeamRole not in user2.roles:
            await self.bot.say(":x: {0} is not on the {1}".format(user2.mention, newTeamRole.mention))
            return

        server_dict = self.get_server_dict(ctx)

        channel = self.get_transaction_channel(server_dict)
        if channel is not None:
            franchiseRole1 = self.get_franchise_role(server_dict, ctx.message.server, newTeamRole)
            franchiseRole2 = self.get_franchise_role(server_dict, ctx.message.server, newTeamRole2)
            if franchiseRole1 is not None and franchiseRole2 is not None:
                prefix1 = self.get_prefix(server_dict, newTeamRole)
                prefix2 = self.get_prefix(server_dict, newTeamRole2)
                if prefix1 is not None and prefix2 is not None:
                    message = "{0} was traded by the {1} to the {2} for {3}".format(user.mention, newTeamRole2.mention, newTeamRole.mention, user2.mention)
                    try:
                        await self.bot.add_roles(user, newTeamRole, franchiseRole1)
                        await self.bot.change_nickname(user, "{0} | {1}".format(prefix1, user.name))
                        await self.bot.remove_roles(user, newTeamRole2, franchiseRole2)
                    except:
                        await self.bot.say(":x: Error trying to handle roles for {0}".format(user.name))
                        return

                    try:
                        await self.bot.add_roles(user2, newTeamRole2, franchiseRole2)
                        await self.bot.change_nickname(user2, "{0} | {1}".format(prefix2, user2.name))
                        await self.bot.remove_roles(user2, newTeamRole, franchiseRole1)
                    except:
                        await self.bot.say(":x: Error trying to handle roles for {0}".format(user2.name))
                        return
                    
                    await self.bot.send_message(channel, message)

    @commands.command(pass_context=True)
    async def sub(self, ctx, user : discord.Member, teamRole : discord.Role):
        """Adds the team role to the user and posts to the assigned channel"""
        server_dict = self.get_server_dict(ctx)

        channel = self.get_transaction_channel(server_dict)
        if channel is not None:
            leagueRole = self.get_league_role(server_dict, ctx.message.server)
            if leagueRole is not None:
                if teamRole in user.roles:
                    await self.bot.remove_roles(user, teamRole)
                    message = "{0} has finished their time as a substitute for the {1}".format(user.name, teamRole.name)
                else:
                    await self.bot.add_roles(user, teamRole, leagueRole)
                    message = "{0} was signed to a temporary contract by the {1}".format(user.mention, teamRole.mention)
                await self.bot.send_message(channel, message)

    def get_server_dict(self, ctx):
        server = ctx.message.server
        self.load_data()
        server_dict = self.config.setdefault(server.id, {})
        return server_dict

    def find_role(self, roles, roleId):
        for role in roles:
            if role.id == roleId:
                return role
        raise LookupError('roleId not found in server roles')

    async def get_franchise_role(self, server_dict, server, teamRole):
        try:
            franchise_dict = server_dict.setdefault("Franchise roles", {})
            gmName = self.get_gm_name(teamRole)
            try:
                franchiseRole = self.find_role(server.roles, franchise_dict[gmName])
                return franchiseRole
            except KeyError:
                await self.bot.say(":x: Franchise role not found for {0}".format(gmName))
                return None
            except LookupError:
                await self.bot.say(":x: Could not find franchise role with id of {0}".format(franchise_dict[gmName]))
                return None
        except KeyError:
            await self.bot.say(":x: Couldn't find franchise role dictionary")
            return None

    async def get_prefix(self, server_dict, teamRole):
        try:
            prefix_dict = server_dict.setdefault("Prefixes", {})
            gmName = self.get_gm_name(teamRole)
            try:
                prefix = prefix_dict[gmName]
                return prefix
            except KeyError:
                await self.bot.say(":x: Prefix not found for {0}".format(gmName))
                return None
        except KeyError:
            await self.bot.say(":x: Couldn't find prefix dictionary")
            return None

    def get_gm_name(self, teamRole):
        return re.findall(r'(?<=\()\w*\b', teamRole.name)[0]

    async def get_transaction_channel(self, server_dict):
        try:
            channelId = server_dict['Transaction Channel']
            try:
                channel = server.get_channel(channelId)
                return channel
            except:
                await self.bot.say(":x: Transaction log channel not found with id of {0}".format(channelId))
                return None
        except KeyError:
            await self.bot.say(":x: Transaction log channel not set")
            return None

    async def get_league_role(self, server_dict, server):
        try:
            leagueRoleId = server_dict['League Role']
            try:
                leagueRole = self.find_role(server.roles, leagueRoleId)
                return leagueRole
            except LookupError:
                await self.bot.say(":x: Could not find league role with id of {0}".format(leagueRoleId))
                return None
        except KeyError:
            await self.bot.say(":x: League role not currently set")
            return None

    # Config
    def check_configs(self):
        self.check_folders()
        self.check_files()

    def check_folders(self):
        if not os.path.exists(self.DATA_FOLDER):
            os.makedirs(self.DATA_FOLDER, exist_ok=True)

    def check_files(self):
        self.check_file(self.CONFIG_FILE_PATH, self.CONFIG_DEFAULT)

    def check_file(self, file, default):
        if not dataIO.is_valid_json(file):
            dataIO.save_json(file, default)

    def load_data(self):
        self.config = dataIO.load_json(self.CONFIG_FILE_PATH)

    def save_data(self):
        dataIO.save_json(self.CONFIG_FILE_PATH, self.config)

def setup(bot):
    bot.add_cog(Transactions(bot))