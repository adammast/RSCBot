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
        server_dict = self.get_server_dict(ctx)
        channel = await self.add_player_to_team(ctx, server_dict, user, teamRole)
        if channel is not None:
            try:
                free_agent_dict = server_dict.setdefault("Free agent roles", {})
                freeAgentRole = self.find_role(ctx.message.server.roles, free_agent_dict[self.get_tier_name(teamRole)])
                if freeAgentRole is None:
                    if(len(free_agent_dict.items()) > 0):
                        for key, value in free_agent_dict.items():
                            for role in user.roles:
                                if role.id == value:
                                    freeAgentRole = role
                                    break
                message = "{0} was signed by the {1}".format(user.mention, teamRole.mention)
                await self.bot.send_message(channel, message)
                if freeAgentRole is not None:
                    await self.bot.remove_roles(user, freeAgentRole)
                await self.bot.say("Done")
            except KeyError:
                await self.bot.say(":x: Free agent role not found in dictionary")
            except LookupError:
                await self.bot.say(":x: Free agent role not found in server")

    @commands.command(pass_context=True)
    async def cut(self, ctx, user : discord.Member, teamRole : discord.Role):
        """Removes the team role and franchise role, and adds the free agent prefix to a user and posts to the assigned channel"""
        server_dict = self.get_server_dict(ctx)
        channel = await self.remove_player_from_team(ctx, server_dict, user, teamRole)
        if channel is not None:
            try:
                free_agent_dict = server_dict.setdefault("Free agent roles", {})
                freeAgentRole = self.find_role(ctx.message.server.roles, free_agent_dict[self.get_tier_name(teamRole)])
                await self.bot.change_nickname(user, "FA | {0}".format(self.get_player_nickname(user)))
                await self.bot.add_roles(user, freeAgentRole)
                message = "{0} was cut by the {1} They will now be on waivers".format(user.mention, teamRole.mention)
                await self.bot.send_message(channel, message)
                await self.bot.say("Done")
            except KeyError:
                await self.bot.say(":x: Free agent role not found in dictionary")
            except LookupError:
                await self.bot.say(":x: Free agent role not found in server")

    @commands.command(pass_context=True)
    async def trade(self, ctx, user : discord.Member, newTeamRole : discord.Role, user2 : discord.Member, newTeamRole2 : discord.Role):
        """Swaps the teams of the two players and announces the trade in the assigned channel"""
        server_dict = self.get_server_dict(ctx)
        await self.remove_player_from_team(ctx, server_dict, user, newTeamRole2)
        await self.remove_player_from_team(ctx, server_dict, user2, newTeamRole)
        await self.add_player_to_team(ctx, server_dict, user, newTeamRole)
        channel = await self.add_player_to_team(ctx, server_dict, user2, newTeamRole2)
        if channel is not None:
            message = "{0} was traded by the {1} to the {2} for {3}".format(user.mention, newTeamRole2.mention, newTeamRole.mention, user2.mention)
            await self.bot.send_message(channel, message)
            await self.bot.say("Done")

    @commands.command(pass_context=True)
    async def sub(self, ctx, user : discord.Member, teamRole : discord.Role):
        """Adds the team role to the user and posts to the assigned channel"""
        server_dict = self.get_server_dict(ctx)

        channel = await self.get_transaction_channel(server_dict, ctx.message.server)
        if channel is not None:
            leagueRole = await self.get_league_role(server_dict, ctx.message.server)
            if leagueRole is not None:
                if teamRole in user.roles:
                    await self.bot.remove_roles(user, teamRole)
                    message = "{0} has finished their time as a substitute for the {1}".format(user.name, teamRole.name)
                else:
                    await self.bot.add_roles(user, teamRole, leagueRole)
                    message = "{0} was signed to a temporary contract by the {1}".format(user.mention, teamRole.mention)
                await self.bot.send_message(channel, message)
                await self.bot.say("Done")

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

    def get_gm_name(self, teamRole):
        try:
            return re.findall(r'(?<=\()\w*\b', teamRole.name)[0]
        except:
            raise LookupError('GM name not found from role {0}'.format(teamRole.name))

    def get_tier_name(self, teamRole):
        try:
            return re.findall(r'\w*\b(?=\))', teamRole.name)[0]
        except:
            raise LookupError('Tier name not found from role {0}'.format(teamRole.name))

    async def add_player_to_team(self, ctx, server_dict, user, teamRole):
        if teamRole in user.roles:
            await self.bot.say(":x: {0} is already on the {1}".format(user.mention, teamRole.mention))
            return False

        channel = await self.get_transaction_channel(server_dict, ctx.message.server)
        if channel is not None:
            leagueRole = await self.get_league_role(server_dict, ctx.message.server)
            if leagueRole is not None:
                franchiseRole = await self.get_franchise_role(server_dict, ctx.message.server, teamRole)
                if franchiseRole is not None:
                    prefix = await self.get_prefix(server_dict, teamRole)
                    if prefix is not None:
                        await self.bot.change_nickname(user, "{0} | {1}".format(prefix, self.get_player_nickname(user)))
                        await self.bot.add_roles(user, teamRole, leagueRole, franchiseRole)
                        return channel


    async def remove_player_from_team(self, ctx, server_dict, user, teamRole):
        if teamRole not in user.roles:
            await self.bot.say(":x: {0} is not on the {1}".format(user.mention, teamRole.mention))
            return

        channel = await self.get_transaction_channel(server_dict, ctx.message.server)
        if channel is not None:
            franchiseRole = await self.get_franchise_role(server_dict, ctx.message.server, teamRole)
            if franchiseRole is not None:
                prefix = await self.get_prefix(server_dict, teamRole)
                if prefix is not None:
                    await self.bot.remove_roles(user, teamRole, franchiseRole)
                    return channel

    def get_player_nickname(self, user : discord.Member):
        if user.nick is not None:
            array = user.nick.split(' | ', 1)
            if len(array) == 2:
                currentNickname = array[1].strip()
            else:
                currentNickname = array[0]
            return currentNickname
        return user.name

    async def get_franchise_role(self, server_dict, server, teamRole):
        try:
            franchise_dict = server_dict.setdefault("Franchise roles", {})
            try:
                gmName = self.get_gm_name(teamRole)
                try:
                    return self.find_role(server.roles, franchise_dict[gmName])
                except KeyError:
                    await self.bot.say(":x: Franchise role not found for {0}".format(gmName))
                except LookupError:
                    await self.bot.say(":x: Could not find franchise role with id of {0}".format(franchise_dict[gmName]))
            except LookupError:
                await self.bot.say('GM name not found from role {0}'.format(teamRole.name))
        except KeyError:
            await self.bot.say(":x: Couldn't find franchise role dictionary")

    async def get_prefix(self, server_dict, teamRole):
        try:
            prefix_dict = server_dict.setdefault("Prefixes", {})
            try:
                gmName = self.get_gm_name(teamRole)
                try:
                    return prefix_dict[gmName]
                except KeyError:
                    await self.bot.say(":x: Prefix not found for {0}".format(gmName))
            except LookupError:
                await self.bot.say('GM name not found from role {0}'.format(teamRole.name))
        except KeyError:
            await self.bot.say(":x: Couldn't find prefix dictionary")

    async def get_transaction_channel(self, server_dict, server):
        try:
            channelId = server_dict['Transaction Channel']
            try:
                return server.get_channel(channelId)
            except:
                await self.bot.say(":x: Transaction log channel not found with id of {0}".format(channelId))
        except KeyError:
            await self.bot.say(":x: Transaction log channel not set")

    async def get_league_role(self, server_dict, server):
        try:
            leagueRoleId = server_dict['League Role']
            try:
                return self.find_role(server.roles, leagueRoleId)
            except LookupError:
                await self.bot.say(":x: Could not find league role with id of {0}".format(leagueRoleId))
        except KeyError:
            await self.bot.say(":x: League role not currently set")

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