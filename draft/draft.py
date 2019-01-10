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
    async def draft(self, ctx, user : discord.Member, teamRole : discord.Role, round: int, pick: int):
        """Assigns the team role and league role to a user when they are drafted and posts to the assigned channel"""
        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        franchiseRole = await self.TRANS_COG.get_franchise_role(server_dict, ctx.message.server, teamRole)
        if franchiseRole in user.roles:
            message = "Round {0} Pick {1}: {2} was kept by the {3}".format(round, pick, user.mention, teamRole.mention)
        else:
            message = "Round {0} Pick {1}: {2} was drafted by the {3}".format(round, pick, user.mention, teamRole.mention)
        currentTeamRole = self.TRANS_COG.get_current_team_role(ctx, user)
        if currentTeamRole is not None and currentTeamRole != teamRole:
            await self.bot.remove_roles(user, currentTeamRole)
        channel = await self.TRANS_COG.add_player_to_team(ctx, server_dict, user, teamRole)
        if channel is not None:
            try:
                free_agent_dict = server_dict.setdefault("Free agent roles", {})
                freeAgentRole = self.TRANS_COG.find_free_agent_role(free_agent_dict, user)
                await self.bot.send_message(channel, message)
                draftEligibleRole = None
                for role in user.roles:
                    if role.name == "Draft Eligible":
                        draftEligibleRole = role
                        break
                if freeAgentRole is not None:
                    await self.bot.remove_roles(user, freeAgentRole)
                if draftEligibleRole is not None:
                    await self.bot.remove_roles(user, draftEligibleRole)
                await self.bot.say("Done")
            except KeyError:
                await self.bot.say(":x: Free agent role not found in dictionary")
            except LookupError:
                await self.bot.say(":x: Free agent role not found in server")
            return

def setup(bot):
    bot.add_cog(Draft(bot))