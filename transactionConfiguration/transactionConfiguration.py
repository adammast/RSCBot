import discord
import os.path
import os
import json

from .utils.dataIO import dataIO
from discord.ext import commands
from cogs.utils import checks

class TransactionConfiguration:
    """Used to set information used across all or most transactions such as the transaction log channel, the league role, 
    and the team prefixes"""

    DATA_FOLDER = "data/transactionConfiguration"
    CONFIG_FILE_PATH = DATA_FOLDER + "/config.json"

    CONFIG_DEFAULT = {}

    def __init__(self, bot):
        self.bot = bot
        self.check_configs()
        self.load_data()

    @commands.command(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def genericAnnounce(self, ctx, message):
        """Posts the message to the transaction log channel"""
        guild = ctx.message.guild
        server_dict = self.get_server_dict(ctx)

        try:
            channelId = server_dict['Transaction Channel']
            channel = guild.get_channel(channelId)
            await channel.send(message)
            await self.bot.say("Done")
        except KeyError:
            await self.bot.say(":x: Transaction log channel not set")

    @commands.command(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def addFreeAgentRole(self, ctx, tier, role : discord.Role):
        """Used to set the free agent roles for the different tiers"""
        server_dict = self.get_server_dict(ctx)
        free_agent_dict = server_dict.setdefault("Free agent roles", {})
            
        try:
            free_agent_dict[tier] = role.id
            self.save_data()
            await self.bot.say("Free agent role for {0} = {1}".format(tier, role.mention))
        except IndexError:
            await self.bot.say(":x: Error adding info to the free agent role dictionary")

    @commands.command(pass_context=True, no_pm=True)
    async def getFreeAgentRoles(self, ctx):
        """Used to get all free agent roles for the different tiers"""
        guild = ctx.message.guild
        server_dict = self.get_server_dict(ctx)
        free_agent_dict = server_dict.setdefault("Free agent roles", {})

        if(len(free_agent_dict.items()) > 0):
            for key, value in free_agent_dict.items():
                try:
                    try:
                        freeAgentRole = self.find_role(guild.roles, value)
                        await self.bot.say("Free agent role for {0} tier = {1}".format(key, freeAgentRole.name))
                    except LookupError:
                        await self.bot.say(":x: Could not find free agent role with id of {0}".format(value))
                except IndexError:
                    await self.bot.say(":x: Error finding key value pair in free agent role dictionary")
        else:
            await self.bot.say(":x: No free agent roles are set in the dictionary")

    @commands.command(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def clearFreeAgentRoles(self, ctx):
        """Used to clear the free agent role dictionary"""
        server_dict = self.get_server_dict(ctx)
        free_agent_dict = server_dict.setdefault("Free agent roles", {})

        try:
            free_agent_dict.clear()
            self.save_data()
            await self.bot.say(":white_check_mark: All free agent roles have been removed from dictionary")
        except:
            await self.bot.say(":x: Something went wrong when trying to clear the free agent role dictionary")

    @commands.command(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def setTransactionLogChannel(self, ctx, tlog : discord.Channel):
        """Assigns the specified channel as the channel where all transactions will be announced"""
        server_dict = self.get_server_dict(ctx)

        try:
            server_dict.setdefault('Transaction Channel', tlog.id)
            self.save_data()
            await self.bot.say(":white_check_mark: Transaction log channel now set to {0}".format(tlog.mention))
        except:
            await self.bot.say(":x: Error setting transaction log channel to {0}".format(tlog.mention))

    @commands.command(pass_context=True, no_pm=True)
    async def getTransactionLogChannel(self, ctx):
        """Gets the transaction-log channel"""
        channel = await self.get_transaction_channel(self.get_server_dict(ctx), ctx.message.guild)
        if(channel is not None):
            await self.bot.say("Transaction log channel currently set to {0}".format(channel.mention))
             

    @commands.command(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def unsetTransactionLogChannel(self, ctx):
        """Unassignes the transaction-log channel"""
        guild = ctx.message.guild
        server_dict = self.get_server_dict(ctx)

        channelId = server_dict.pop('Transaction Channel', None)
        if channelId:
            channel = guild.get_channel(channelId)
            self.save_data()
            await self.bot.say(":white_check_mark: Transaction log channel no longer set to {0}".format(channel.mention))
        else:
            await self.bot.say(":x: Transaction log channel has not been set")

    @commands.command(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def setDraftLogChannel(self, ctx, dlog : discord.Channel):
        """Assigns the specified channel as the channel where all draft transactions will be announced"""
        server_dict = self.get_server_dict(ctx)

        try:
            server_dict.setdefault('Draft Channel', dlog.id)
            self.save_data()
            await self.bot.say(":white_check_mark: Draft log channel now set to {0}".format(dlog.mention))
        except:
            await self.bot.say(":x: Error setting draft log channel to {0}".format(dlog.mention))

    @commands.command(pass_context=True, no_pm=True)
    async def getDraftLogChannel(self, ctx):
        """Gets the draft-log channel"""
        channel = await self.get_draft_channel(self.get_server_dict(ctx), ctx.message.guild)
        if(channel is not None):
            await self.bot.say("Draft log channel currently set to {0}".format(channel.mention))
             

    @commands.command(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def unsetDraftLogChannel(self, ctx):
        """Unassignes the draft-log channel"""
        guild = ctx.message.guild
        server_dict = self.get_server_dict(ctx)

        channelId = server_dict.pop('Draft Channel', None)
        if channelId:
            channel = guild.get_channel(channelId)
            self.save_data()
            await self.bot.say(":white_check_mark: Draft log channel no longer set to {0}".format(channel.mention))
        else:
            await self.bot.say(":x: Draft log channel has not been set")

    def find_role(self, roles, roleId):
        for role in roles:
            if role.id == roleId:
                return role
        raise LookupError('roleId not found in server roles')

    def find_role_by_name(self, roles, roleName):
        for role in roles:
            if role.name == roleName:
                return role
        return None

    def get_server_dict(self, ctx):
        self.load_data()
        server_dict = self.config.setdefault(ctx.message.guild.id, {})
        return server_dict

    async def get_transaction_channel(self, server_dict, guild):
        try:
            channelId = server_dict['Transaction Channel']
            try:
                return guild.get_channel(channelId)
            except:
                await self.bot.say(":x: Transaction log channel not found with id of {0}".format(channelId))
        except KeyError:
            await self.bot.say(":x: Transaction log channel not set")

    async def get_draft_channel(self, server_dict, guild):
        try:
            channelId = server_dict['Draft Channel']
            try:
                return guild.get_channel(channelId)
            except:
                await self.bot.say(":x: Draft log channel not found with id of {0}".format(channelId))
        except KeyError:
            await self.bot.say(":x: Draft log channel not set")

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
        # print("CONFIG_COG: Saving data:")
        # print(json.dumps(self.config, indent=4, sort_keys=True))
        dataIO.save_json(self.CONFIG_FILE_PATH, self.config)

def setup(bot):
    bot.add_cog(TransactionConfiguration(bot))