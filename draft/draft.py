import discord
import re

from discord.ext import commands

class Draft:
    """Used to draft players onto teams and give the the appropriate roles"""

    CONFIG_COG = None
    TRANS_COG = None

    def __init__(self, bot):
        self.bot = bot
        self.CONFIG_COG = self.bot.get_cog("TransactionConfiguration")
        self.TRANS_COG = self.bot.get_cog("Transactions")

    @commands.command(pass_context=True)
    async def draft(self, ctx, user : discord.Member, teamRole : discord.Role):
        """Assigns the team role and league role to a user when they are drafted and posts to the assigned channel"""
        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        if teamRole in user.roles:
            message = "{0} was kept by the {1}".format(user.mention, teamRole.mention)
        else:
            message = "{0} was drafted by the {1}".format(user.mention, teamRole.mention)
        channel = await self.TRANS_COG.add_player_to_team(ctx, server_dict, user, teamRole)
        if channel is not None:
            try:
                free_agent_dict = server_dict.setdefault("Free agent roles", {})
                freeAgentRole = self.TRANS_COG.find_free_agent_role(free_agent_dict, user)
                draftEligibleRole = await self.get_draft_eligible_role(server_dict, ctx.message.server)
                await self.bot.send_message(channel, message)
                if freeAgentRole is not None:
                    await self.bot.remove_roles(user, freeAgentRole)
                if draftEligibleRole in user.roles:
                    await self.bot.remove_roles(user, draftEligibleRole)
                await self.bot.say("Done")
            except KeyError:
                await self.bot.say(":x: Free agent role not found in dictionary")
            except LookupError:
                await self.bot.say(":x: Free agent role not found in server")
            return

    @commands.command(pass_context=True)
    async def setDraftEligibleRole(self, ctx, draftEligibleRole : discord.Role):
        """Assigns the specified role as the "Draft Eligible" role so it can be removed from all the players that are drafted"""
        server_dict = self.CONFIG_COG.get_server_dict(ctx)

        try:
            server_dict.setdefault('Draft Eligible Role', draftEligibleRole.id)
            self.CONFIG_COG.save_data()
            await self.bot.say(":white_check_mark: Draft eligible role now set to {0}".format(draftEligibleRole.name))
        except:
            await self.bot.say(":x: Error setting draft eligible role to {0}".format(draftEligibleRole.name))

    @commands.command(pass_context=True)
    async def getDraftEligibleRole(self, ctx):
        """Gets the draft eligible role"""
        draftEligibleRole = await self.get_draft_eligible_role(self.CONFIG_COG.get_server_dict(ctx), ctx.message.server)
        if(draftEligibleRole):
            await self.bot.say("Draft eligible role currently set to {0}".format(draftEligibleRole.name))
            

    @commands.command(pass_context=True)
    async def unsetDraftEligibleRole(self, ctx):
        """Unassignes the draft eligible role"""
        server = ctx.message.server
        server_dict = self.CONFIG_COG.get_server_dict(ctx)

        draftEligibleRoleId = server_dict.pop('Draft Eligible Role', None)
        if draftEligibleRoleId:
            try:
                draftEligibleRole = self.CONFIG_COG.find_role(server.roles, draftEligibleRoleId)
            except LookupError:
                await self.bot.say(":x: Could not find role with id of {0}".format(draftEligibleRoleId))
            else:
                self.CONFIG_COG.save_data()
                await self.bot.say(":white_check_mark: Draft eligible role no longer set to {0}".format(draftEligibleRole.name))
        else:
            await self.bot.say(":x: Draft eligible role has not been set")

    async def get_draft_eligible_role(self, server_dict, server):
        try:
            draftEligibleRoleId = server_dict['Draft Eligible Role']
            try:
                return self.CONFIG_COG.find_role(server.roles, draftEligibleRoleId)
            except LookupError:
                await self.bot.say(":x: Could not find draft eligible role with id of {0}".format(draftEligibleRoleId))
        except KeyError:
            await self.bot.say(":x: Draft eligible role not currently set")

def setup(bot):
    bot.add_cog(Draft(bot))