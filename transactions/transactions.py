import discord
import re

from discord.ext import commands

class Transactions:
    """Used to set franchise and role prefixes and give to members in those franchises or with those roles"""
    
    CONFIG_COG = None

    def __init__(self, bot):
        self.bot = bot
        self.CONFIG_COG = self.bot.get_cog("TransactionConfiguration")
        self.TEAM_MANAGER = self.bot.get_cog("TeamManager")

    @commands.command(pass_context=True, no_pm=True)
    async def draft(self, ctx, user: discord.Member, team_name: str, round: int = None, pick: int = None):
        """Assigns the franchise, tier, and league role to a user when they are drafted and posts to the assigned channel"""
        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        franchise_role, tier_role = self.TEAM_MANAGER._roles_for_team(ctx, team_name)
        if franchise_role in user.roles:
            message = "Round {0} Pick {1}: {2} was kept by the {3}".format(round, pick, user.mention, team_name)
        else:
            message = "Round {0} Pick {1}: {2} was drafted by the {3}".format(round, pick, user.mention, team_name)

        channel = await self.add_player_to_team(ctx, server_dict, user, team_name)
        if channel is not None:
            try:
                free_agent_dict = server_dict.setdefault("Free agent roles", {})
                freeAgentRole = self.find_free_agent_role(free_agent_dict, user)
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


    @commands.command(pass_context=True, no_pm=True)
    async def sign(self, ctx, user: discord.Member, team_name: str):
        """Assigns the team role, franchise role and prefix to a user when they are signed and posts to the assigned channel"""
        franchise_role, tier_role = self.TEAM_MANAGER._roles_for_team(ctx, team_name)
        if franchise_role in user.roles and tier_role in user.roles:
            await self.bot.say(":x: {0} is already on the {1}".format(user.mention, team_name))
            return

        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        channel = await self.add_player_to_team(ctx, server_dict, user, team_name)
        if channel is not None:
           try:
               free_agent_dict = server_dict.setdefault("Free agent roles", {})
               freeAgentRole = self.find_free_agent_role(free_agent_dict, user)
               message = "{0} was signed by the {1}".format(user.mention, team_name)
               await self.bot.send_message(channel, message)
               if freeAgentRole is not None:
                   await self.bot.remove_roles(user, freeAgentRole)
               await self.bot.say("Done")
           except KeyError:
               await self.bot.say(":x: Free agent role not found in dictionary")
           except LookupError:
               await self.bot.say(":x: Free agent role not found in server")

    @commands.command(pass_context=True, no_pm=True)
    async def cut(self, ctx, user : discord.Member, team_name: str, freeAgentRole: discord.Role = None):
        """Removes the team role and franchise role. Adds the free agent prefix to a user and posts to the assigned channel"""
        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        channel = await self.remove_player_from_team(ctx, server_dict, user, team_name)
        if channel is not None:
            try:
                if freeAgentRole is None:
                    freeAgentRole = self.CONFIG_COG.find_role_by_name(ctx.message.server.roles, "{0}FA".format(self.get_current_tier_role(ctx, user).name))
                await self.bot.change_nickname(user, "FA | {0}".format(self.get_player_nickname(user)))
                await self.bot.add_roles(user, freeAgentRole)
                message = "{0} was cut by the {1}".format(user.mention, team_name)
                await self.bot.send_message(channel, message)
                await self.bot.say("Done")
            except KeyError:
                await self.bot.say(":x: Free agent role not found in dictionary")
            except LookupError:
                await self.bot.say(":x: Free agent role not found in server")

    @commands.command(pass_context=True, no_pm=True)
    async def trade(self, ctx, user: discord.Member, new_team_name: str, user_2: discord.Member, new_team_name_2: str):
        """Swaps the teams of the two players and announces the trade in the assigned channel"""
        franchise_role_1, tier_role_1 = self.TEAM_MANAGER._roles_for_team(ctx, new_team_name)
        franchise_role_2, tier_role_2 = self.TEAM_MANAGER._roles_for_team(ctx, new_team_name_2)
        if franchise_role_1 in user.roles and tier_role_1 in user.roles:
            await self.bot.say(":x: {0} is already on the {1}".format(user.mention, new_team_name))
            return
        if franchise_role_2 in user_2.roles and tier_role_2 in user_2.roles:
            await self.bot.say(":x: {0} is already on the {1}".format(user_2.mention, new_team_name_2))
            return

        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        await self.remove_player_from_team(ctx, server_dict, user, new_team_name_2)
        await self.remove_player_from_team(ctx, server_dict, user_2, new_team_name)
        await self.add_player_to_team(ctx, server_dict, user, new_team_name)
        channel = await self.add_player_to_team(ctx, server_dict, user_2, new_team_name_2)
        if channel is not None:
           message = "{0} was traded by the {1} to the {2} for {3}".format(user.mention, new_team_name_2, new_team_name, user_2.mention)
           await self.bot.send_message(channel, message)
           await self.bot.say("Done")

    @commands.command(pass_context=True, no_pm=True)
    async def sub(self, ctx, user: discord.Member, team_name: str):
        """Adds the team role to the user and posts to the assigned channel"""
        server_dict = self.CONFIG_COG.get_server_dict(ctx)

        channel = await self.CONFIG_COG.get_transaction_channel(server_dict, ctx.message.server)
        if channel is not None:
            leagueRole = self.CONFIG_COG.find_role_by_name(ctx.message.server.roles, "League")
            if leagueRole is not None:
                franchise_role, tier_role = self.TEAM_MANAGER._roles_for_team(ctx, team_name)
                if franchise_role in user.roles and tier_role in user.roles:
                    await self.bot.remove_roles(user, franchise_role, tier_role)
                    message = "{0} has finished their time as a substitute for the {1}".format(user.name, team_name)
                else:
                    await self.bot.add_roles(user, franchise_role, tier_role, leagueRole)
                    message = "{0} was signed to a temporary contract by the {1}".format(user.mention, team_name)
                await self.bot.send_message(channel, message)
                await self.bot.say("Done")

    @commands.command(pass_context=True, no_pm=True)
    async def promote(self, ctx, user: discord.Member, team_name: str):
        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        old_team_name = self.get_current_team_name(ctx, user)
        if old_team_name is not None:
            if self.TEAM_MANAGER._roles_for_team(ctx, old_team_name)[0] != self.TEAM_MANAGER._roles_for_team(ctx, team_name)[0]:
                await self.bot.say(":x: {0} is not in the same franchise as {1}'s current team, the {2}".format(team_name.name, user.name, old_team_name))
                return
            await self.remove_player_from_team(ctx, server_dict, user, old_team_name)
            channel = await self.add_player_to_team(ctx, server_dict, user, team_name)
            if channel:
               message = "{0} was promoted to the {1}".format(user.mention, team_name)
               await self.bot.send_message(channel, message)
               await self.bot.say("Done")
        else:
            await self.bot.say("Either {0} isn't on a team right now or his current team can't be found".format(user.name))

    ## NO LONGER NEEDED
    # @commands.command(pass_context=True, no_pm=True)
    # async def relegate(self, ctx, user: discord.Member, team_name: str):
    #     server_dict = self.CONFIG_COG.get_server_dict(ctx)
    #     old_team_name = self.get_current_team_name(ctx, user)
    #     if old_team_name is not None:
    #         if self.TEAM_MANAGER._roles_for_team(ctx, old_team_name)[0] != self.TEAM_MANAGER._roles_for_team(ctx, team_name)[0]:
    #             await self.bot.say(":x: {0} is not in the same franchise as {1}'s current team, the {2}".format(team_name.name, user.name, old_team_name))
    #             return
    #         await self.remove_player_from_team(ctx, server_dict, user, old_team_name)
    #         channel = await self.add_player_to_team(ctx, server_dict, user, team_name)
    #         if channel:
    #            message = "{0} was relegated to the {1}".format(user.mention, team_name)
    #            await self.bot.send_message(channel, message)
    #            await self.bot.say("Done")
    #     else:
    #         await self.bot.say("Either {0} isn't on a team right now or his current team can't be found".format(user.name))

    def get_gm_name(self, teamRole):
        try:
            return re.findall(r'(?<=\().*(?=\))', teamRole.name)[0].split('-')[0].strip()
        except:
            raise LookupError('GM name not found from role {0}'.format(teamRole.name))

    def get_current_team_name(self, ctx, user: discord.Member):
        tier_role = self.get_current_tier_role(ctx, user)
        franchise_role = self.get_current_franchise_role(user)
        return self.TEAM_MANAGER._find_team_name(ctx, franchise_role, tier_role)


    def get_current_tier_role(self, ctx, user: discord.Member):
        tierList = self.TEAM_MANAGER._tiers(ctx)
        for role in user.roles:
            if role.name in tierList:
                return role
        return None

    def get_current_franchise_role(self, user: discord.Member):
        for role in user.roles:
            try:
                gmNameFromRole = re.findall(r'(?<=\().*(?=\))', role.name)[0]
                if gmNameFromRole:
                    return role
            except:
                continue

    def find_free_agent_role(self, free_agent_dict, user):
        if(len(free_agent_dict.items()) > 0):
            for value in free_agent_dict.items():
                for role in user.roles:
                    if role.id == value[1]:
                        return role
        return None

    async def add_player_to_team(self, ctx, server_dict, user, team_name):
        franchise_role, tier_role = self.TEAM_MANAGER._roles_for_team(ctx, team_name)
        if franchise_role in user.roles and tier_role in user.roles:
            await self.bot.say(":x: {0} is already on the {1}".format(user.mention, team_name))
            return

        channel = await self.CONFIG_COG.get_transaction_channel(server_dict, ctx.message.server)
        if channel is not None:
            leagueRole = self.CONFIG_COG.find_role_by_name(ctx.message.server.roles, "League")
            if leagueRole is not None:
                prefix = await self.get_prefix(server_dict, franchise_role)
                if prefix is not None:
                    currentTier = self.get_current_tier_role(ctx, user)
                    if currentTier is not None and currentTier != tier_role:
                        await self.bot.remove_roles(currentTier)
                    await self.bot.change_nickname(user, "{0} | {1}".format(prefix, self.get_player_nickname(user)))
                    await self.bot.add_roles(user, tier_role, leagueRole, franchise_role)
                    return channel


    async def remove_player_from_team(self, ctx, server_dict, user, team_name):
        franchise_role, tier_role = self.TEAM_MANAGER._roles_for_team(ctx, team_name)
        if franchise_role not in user.roles or tier_role not in user.roles:
            await self.bot.say(":x: {0} is not on the {1}".format(user.mention, team_name))
            return

        channel = await self.CONFIG_COG.get_transaction_channel(server_dict, ctx.message.server)
        if channel is not None:
            if franchise_role is not None:
                prefix = await self.get_prefix(server_dict, franchise_role)
                if prefix is not None:
                    await self.bot.remove_roles(user, franchise_role)
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

    async def get_prefix(self, server_dict, franchiseRole: discord.Role):
        try:
            prefix_dict = server_dict.setdefault("Prefixes", {})
            try:
                gmName = self.get_gm_name(franchiseRole)
                try:
                    return prefix_dict[gmName]
                except KeyError:
                    await self.bot.say(":x: Prefix not found for {0}".format(gmName))
            except LookupError:
                await self.bot.say('GM name not found from role {0}'.format(franchiseRole.name))
        except KeyError:
            await self.bot.say(":x: Couldn't find prefix dictionary")

def setup(bot):
    bot.add_cog(Transactions(bot))