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
    async def draft(self, ctx, user : discord.Member, franchiseRole : discord.Role, tierRole : discord.Role, round: int = None, pick: int = None):
        """Assigns the franchise, tier, and league role to a user when they are drafted and posts to the assigned channel"""
        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        if franchiseRole in user.roles:
            message = "Round {0} Pick {1}: {2} was kept by the {3}".format(round, pick, user.mention, franchiseRole.mention)
        else:
            message = "Round {0} Pick {1}: {2} was drafted by the {3}".format(round, pick, user.mention, franchiseRole.mention)

        channel = await self.add_player_to_team(ctx, server_dict, user, franchiseRole, tierRole)
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
    async def sign(self, ctx, user : discord.Member, teamRole : discord.Role):
        """Assigns the team role, franchise role and prefix to a user when they are signed and posts to the assigned channel"""
        if teamRole in user.roles:
            await self.bot.say(":x: {0} is already on the {1}".format(user.mention, teamRole.mention))
            return

        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        #channel = await self.add_player_to_team(ctx, server_dict, user, teamRole)
        #if channel is not None:
        #    try:
        #        free_agent_dict = server_dict.setdefault("Free agent roles", {})
        #        freeAgentRole = self.find_free_agent_role(free_agent_dict, user)
        #        message = "{0} was signed by the {1}".format(user.mention, teamRole.mention)
        #        await self.bot.send_message(channel, message)
        #        if freeAgentRole is not None:
        #            await self.bot.remove_roles(user, freeAgentRole)
        #        await self.bot.say("Done")
        #    except KeyError:
        #        await self.bot.say(":x: Free agent role not found in dictionary")
        #    except LookupError:
        #        await self.bot.say(":x: Free agent role not found in server")

    @commands.command(pass_context=True, no_pm=True)
    async def cut(self, ctx, user : discord.Member, teamRole : discord.Role, freeAgentRole : discord.Role = None):
        """Removes the team role and franchise role. Adds the free agent prefix to a user and posts to the assigned channel"""
        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        channel = await self.remove_player_from_team(ctx, server_dict, user, teamRole)
        if channel is not None:
            try:
                if freeAgentRole is None:
                    freeAgentRole = self.CONFIG_COG.find_role_by_name(ctx.message.server.roles, "{0}FA".format(self.get_tier_name(teamRole)))
                await self.bot.change_nickname(user, "FA | {0}".format(self.get_player_nickname(user)))
                await self.bot.add_roles(user, freeAgentRole)
                message = "{0} was cut by the {1} They will now be on waivers".format(user.mention, teamRole.mention)
                await self.bot.send_message(channel, message)
                await self.bot.say("Done")
            except KeyError:
                await self.bot.say(":x: Free agent role not found in dictionary")
            except LookupError:
                await self.bot.say(":x: Free agent role not found in server")

    @commands.command(pass_context=True, no_pm=True)
    async def trade(self, ctx, user : discord.Member, newTeamRole : discord.Role, user2 : discord.Member, newTeamRole2 : discord.Role):
        """Swaps the teams of the two players and announces the trade in the assigned channel"""
        if newTeamRole in user.roles:
            await self.bot.say(":x: {0} is already on the {1}".format(user.mention, newTeamRole.mention))
            return
        if newTeamRole2 in user2.roles:
            await self.bot.say(":x: {0} is already on the {1}".format(user2.mention, newTeamRole2.mention))
            return

        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        await self.remove_player_from_team(ctx, server_dict, user, newTeamRole2)
        await self.remove_player_from_team(ctx, server_dict, user2, newTeamRole)
        #await self.add_player_to_team(ctx, server_dict, user, newTeamRole)
        #channel = await self.add_player_to_team(ctx, server_dict, user2, newTeamRole2)
        #if channel is not None:
        #    message = "{0} was traded by the {1} to the {2} for {3}".format(user.mention, newTeamRole2.mention, newTeamRole.mention, user2.mention)
        #    await self.bot.send_message(channel, message)
        #    await self.bot.say("Done")

    @commands.command(pass_context=True, no_pm=True)
    async def sub(self, ctx, user : discord.Member, teamRole : discord.Role):
        """Adds the team role to the user and posts to the assigned channel"""
        server_dict = self.CONFIG_COG.get_server_dict(ctx)

        channel = await self.CONFIG_COG.get_transaction_channel(server_dict, ctx.message.server)
        if channel is not None:
            leagueRole = self.CONFIG_COG.find_role_by_name(ctx.message.server.roles, "League")
            if leagueRole is not None:
                if teamRole in user.roles:
                    await self.bot.remove_roles(user, teamRole)
                    message = "{0} has finished their time as a substitute for the {1}".format(user.name, teamRole.name)
                else:
                    await self.bot.add_roles(user, teamRole, leagueRole)
                    message = "{0} was signed to a temporary contract by the {1}".format(user.mention, teamRole.mention)
                await self.bot.send_message(channel, message)
                await self.bot.say("Done")

    @commands.command(pass_context=True, no_pm=True)
    async def promote(self, ctx, user : discord.Member, teamRole : discord.Role):
        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        oldTeamRole = self.get_current_team_role(ctx, user)
        if oldTeamRole is not None:
            if await self.get_franchise_role(server_dict, ctx.message.server, oldTeamRole) != await self.get_franchise_role(server_dict, ctx.message.server, teamRole):
                await self.bot.say(":x: {0} is not in the same franchise as {1}'s current team, the {2}".format(teamRole.name, user.name, oldTeamRole.name))
                return
            await self.remove_player_from_team(ctx, server_dict, user, oldTeamRole)
            #channel = await self.add_player_to_team(ctx, server_dict, user, franchiseRole, tierRole)
            #if channel:
            #    message = "{0} was promoted to the {1}".format(user.mention, teamRole.mention)
            #    await self.bot.send_message(channel, message)
            #    await self.bot.say("Done")
        else:
            await self.bot.say("Either {0} isn't on a team right now or his current team can't be found".format(user.name))

    @commands.command(pass_context=True, no_pm=True)
    async def relegate(self, ctx, user : discord.Member, teamRole : discord.Role):
        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        oldTeamRole = self.get_current_team_role(ctx, user)
        if oldTeamRole is not None:
            if await self.get_franchise_role(server_dict, ctx.message.server, oldTeamRole) != await self.get_franchise_role(server_dict, ctx.message.server, teamRole):
                await self.bot.say(":x: {0} is not in the same franchise as {1}'s current team, the {2}".format(teamRole.name, user.name, oldTeamRole.name))
                return
            await self.remove_player_from_team(ctx, server_dict, user, oldTeamRole)
            #channel = await self.add_player_to_team(ctx, server_dict, user, franchiseRole, tierRole)
            #if channel:
            #    message = "{0} was relegated to the {1}".format(user.mention, teamRole.mention)
            #    await self.bot.send_message(channel, message)
            #    await self.bot.say("Done")
        else:
            await self.bot.say("Either {0} isn't on a team right now or his current team can't be found".format(user.name))

    def get_gm_name(self, teamRole):
        try:
            return re.findall(r'(?<=\().*(?=\))', teamRole.name)[0].split('-')[0].strip()
        except:
            raise LookupError('GM name not found from role {0}'.format(teamRole.name))

    ## DEPRECATED
    def get_tier_name(self, teamRole):
        try:
            return re.findall(r'\w*\b(?=\))', teamRole.name)[0]
        except:
            return None

    ## DEPRECATED
    def get_current_team_role(self, ctx, user : discord.Member):
        tierList = self.TEAM_MANAGER._tiers(ctx)
        for role in user.roles:
            tierName = self.get_tier_name(role)
            if tierName is not None:
                if tierName in tierList:
                    return role

    def get_current_tier_role(self, ctx, user : discord.Member):
        tierList = self.TEAM_MANAGER._tiers(ctx)
        for role in user.roles:
            if role.name in tierList:
                return role
        return None

    def find_free_agent_role(self, free_agent_dict, user):
        if(len(free_agent_dict.items()) > 0):
            for value in free_agent_dict.items():
                for role in user.roles:
                    if role.id == value[1]:
                        return role
        return None

    async def add_player_to_team(self, ctx, server_dict, user, franchiseRole, tierRole):
        channel = await self.CONFIG_COG.get_transaction_channel(server_dict, ctx.message.server)
        if channel is not None:
            leagueRole = self.CONFIG_COG.find_role_by_name(ctx.message.server.roles, "League")
            if leagueRole is not None:
                prefix = await self.get_prefix(server_dict, franchiseRole)
                if prefix is not None:
                    currentTier = self.get_current_tier_role(ctx, user)
                    if currentTier is not None and currentTier != tierRole:
                        await self.bot.remove_roles(currentTier)
                    await self.bot.change_nickname(user, "{0} | {1}".format(prefix, self.get_player_nickname(user)))
                    await self.bot.add_roles(user, tierRole, leagueRole, franchiseRole)
                    return channel


    async def remove_player_from_team(self, ctx, server_dict, user, teamRole):
        if teamRole not in user.roles:
            await self.bot.say(":x: {0} is not on the {1}".format(user.mention, teamRole.mention))
            return

        channel = await self.CONFIG_COG.get_transaction_channel(server_dict, ctx.message.server)
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

    ## DEPRECATED
    async def get_franchise_role(self, server_dict, server, teamRole):
        try:
            gmName = self.get_gm_name(teamRole)
            for role in server.roles:
                try:
                    gmNameFromRole = re.findall(r'(?<=\().*(?=\))', role.name)[0]
                    if gmNameFromRole == gmName:
                        return role
                except:
                    message = ":x: Franchise role not found for {0}".format(gmName)
            await self.bot.say(message)
        except LookupError:
            await self.bot.say('GM name not found from role {0}'.format(teamRole.name))

    async def get_prefix(self, server_dict, franchiseRole : discord.Role):
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