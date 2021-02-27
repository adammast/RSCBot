import discord
import csv
import os

from redbot.core import commands
from redbot.core import Config
from redbot.core import checks
from discord import File
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions

defaults = {"DraftEligibleMessage": None}

class BulkRoleManager(commands.Cog):
    """Used to manage roles role for large numbers of members"""
    
    PERM_FA_ROLE = "PermFA"

    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567897, force_registration=True)
        self.config.register_guild(**defaults)
        self.team_manager_cog = bot.get_cog("TeamManager")
        self.discord_bot = bot

    @commands.command()
    @commands.guild_only()
    async def getAllWithRole(self, ctx, role: discord.Role, getNickname = False):
        """Prints out a list of members with the specific role"""
        count = 0
        messages = []
        message = ""
        await ctx.send("Players with {0} role:\n".format(role.name))
        for member in role.members:
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
            if message:
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
        for member in role.members:
            await member.remove_roles(role)
            empty = False
        if empty:
            await ctx.send(":x: Nobody had the {0} role".format(role.mention))
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
    @checks.admin_or_permissions(manage_roles=True)
    async def removeRole(self, ctx, role : discord.Role, *userList):
        """Removes the role from every member that can be found from the userList"""
        empty = True
        removed = 0
        notHave = 0
        notFound = 0
        message = ""
        for user in userList:
            try:
                member = await commands.MemberConverter().convert(ctx, user)
                if member in ctx.guild.members:
                    if role in member.roles:
                        await member.remove_roles(role)
                        removed += 1
                    else:
                        notHave += 1
                    empty = False
            except:
                if notFound == 0:
                    message += "Couldn't find:\n"
                message += "{0}\n".format(user)
                notFound += 1
        if empty:
            message += ":x: Nobody had the {0} role removed".format(role.name)
        else:
           message += ":white_check_mark: {0} role removed from everyone that was found from list".format(role.name)
        if notFound > 0:
            message += ". {0} user(s) were not found".format(notFound)
        if notHave > 0:
            message += ". {0} user(s) didn't have the role".format(notHave)
        if removed > 0:
            message += ". {0} user(s) had the role removed".format(removed)
        await ctx.send(message)

    @commands.command(aliases=["addMissingServerRoles"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def addRequiredServerRoles(self, ctx):
        """Adds any missing roles required for the bulkRoleManager cog to function properly."""
        required_roles = ["Draft Eligible", "League", "Spectator", "Former Player"]
        found = []
        for role in ctx.guild.roles:
            if role.name in required_roles:
                found.append(role.name)
                required_roles.remove(role.name)
        
        if required_roles:
            for role_name in required_roles:
                await ctx.guild.create_role(name=role_name)
            await ctx.send("The following roles have been added: {0}".format(", ".join(required_roles)))
            return
        await ctx.send("All required roles already exist in the server.")

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
        formerPlayerRole = None
        message = ""
        for role in ctx.guild.roles:
            if role.name == "Draft Eligible":
                deRole = role
            elif role.name == "League":
                leagueRole = role
            elif role.name == "Spectator":
                spectatorRole = role
            elif role.name == "Former Player":
                formerPlayerRole = role
            if leagueRole and deRole and spectatorRole and formerPlayerRole:
                break

        if deRole is None or leagueRole is None or spectatorRole is None or formerPlayerRole is None:
            await ctx.send(":x: Couldn't find either the Draft Eligible, League, Spectator, or Former Player role in the server. Use `{0}addRequiredServerRoles` to add these roles.".format(ctx.prefix))
            return

        for user in userList:
            try:
                member = await commands.MemberConverter().convert(ctx, user)
            except:
                message += "Couldn't find: {0}\n".format(user)
                notFound += 1
                continue
            if member in ctx.guild.members:
                if leagueRole in member.roles:
                    msg = await ctx.send("{0} already has the league role, are you sure you want to make him a DE?".format(member.mention))
                    start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)

                    pred = ReactionPredicate.yes_or_no(msg, ctx.author)
                    await ctx.bot.wait_for("reaction_add", check=pred)
                    if pred.result is False:
                        await ctx.send("{0} not made DE.".format(member.name))
                        had += 1
                        continue
                    else:
                        await ctx.send("You will need to manually remove any team or free agent roles if {0} has any.".format(member.mention))

                await member.add_roles(deRole, leagueRole)
                added += 1
                await member.edit(nick="{0} | {1}".format("DE", self.get_player_nickname(member)))
                await member.remove_roles(spectatorRole, formerPlayerRole)
                deMessage = await self._draft_eligible_message(ctx)
                if deMessage:
                    # await member.send(deMessage)
                    await self._send_member_message(ctx, member, deMessage)
                    
                empty = False
            
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
    @checks.admin_or_permissions(manage_guild=True)
    async def makePermFA(self, ctx, tier: str, *userList):
        """Makes each member that can be found from the userList a permanent Free Agent for the given tier"""
        role_names_to_add = [self.PERM_FA_ROLE, "League", tier, "{0}FA".format(tier)]
        roles_to_add = []
        tiers = await self.team_manager_cog.tiers(ctx)
        for role in ctx.guild.roles:
            if role.name in role_names_to_add:
                roles_to_add.append(role)
                role_names_to_add.remove(role.name)
                if role.name == "League":
                    leagueRole = role
        
        if role_names_to_add:
            await ctx.send(":x: The following roles could not be found: {0}".format(", ".join(role_names_to_add)))
            return False

        empty = True
        notFound = 0
        had = 0
        added = 0
        message = ""
        for user in userList:
            try:
                member = await commands.MemberConverter().convert(ctx, user)
            except:
                message += "Couldn't find: {0}\n".format(user)
                notFound += 1
                continue
            if member in ctx.guild.members:
                empty = False
                tier_changed = True
                old_tier_role = None
                if leagueRole in member.roles:
                    old_tier_role = await self.team_manager_cog.get_current_tier_role(ctx, member)
                    if old_tier_role in member.roles and old_tier_role in roles_to_add:
                        tier_changed = False
                        had += 1
                        added -= 1  # remove double count of had/added

                if tier_changed:
                    action = "assigned"
                    if old_tier_role and old_tier_role not in roles_to_add:
                        old_tier_fa_role = self.team_manager_cog._find_role_by_name(ctx, "{0}FA".format(old_tier_role.name))
                        rm_roles = [old_tier_role, old_tier_fa_role]
                        await member.remove_roles(*rm_roles)
                        action = "promoted"
                    tier_change_msg = ("Congrats! Due to your recent ranks you've been {0} to our {1} tier! "
                    "You'll only be allowed to play in that tier or any tier above it for the remainder of this "
                    "season. If you have any questions please let an admin know."
                    "\n\nIf you checked in already for the next match day, please use the commands `[p]co` to check "
                    "out and then `[p]ci` to check in again for your new tier.").format(action, tier)
                    await self._send_member_message(ctx, member, tier_change_msg)
                
                if self.get_player_nickname(member)[:5] != "FA | ":
                    try:
                        await member.edit(nick="{0} | {1}".format("FA", self.get_player_nickname(member)))
                    except (discord.errors.Forbidden, discord.errors.HTTPException):
                        await ctx.send("Cannot set nickname for {0}".format(member.name))

                await member.add_roles(*roles_to_add)
                added += 1
        
        if len([userList]) and not empty:
            message = "{0} members processed...\n".format(len([userList])) + message
        if empty:
            message += ":x: Nobody was set as a {0} permanent FA".format(tier)
        else:
           message += ":white_check_mark: All members found are now {0} permanent FAs.".format(tier)
        if notFound:
            message += ". {0} user(s) were not found".format(notFound)
        if had:
            message += ". {0} user(s) were already in this tier.".format(had)
        if added:
            message += ". {0} user(s) had the role added to them".format(added)
        await ctx.send(message)       

    @commands.command(aliases=["retirePlayer", "retirePlayers", "setFormerPlayer"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def retire(self, ctx, *userList):
        """Removes league roles and adds 'Former Player' role for every member that can be found from the userList"""
        empty = True
        retired = 0
        notFound = 0
        message = ""
        former_player_str = "Former Player"
        former_player_role = self.team_manager_cog._find_role_by_name(ctx, former_player_str)

        if not former_player_role:
            former_player_role = await self.team_manager_cog.create_role(ctx, former_player_str)

        roles_to_remove = [
            self.team_manager_cog._find_role_by_name(ctx, "League"),
            self.team_manager_cog._find_role_by_name(ctx, "Free Agent"),
            self.team_manager_cog._find_role_by_name(ctx, self.PERM_FA_ROLE)
        ]
        tiers = await self.team_manager_cog.tiers(ctx)
        for tier in tiers:
            tier_role = self.team_manager_cog._get_tier_role(ctx, tier)
            if tier_role:
                tier_fa_role = self.team_manager_cog._find_role_by_name(ctx, "{0}FA".format(tier))
            roles_to_remove.append(tier_role)
            roles_to_remove.append(tier_fa_role)

        for user in userList:
            try:
                member = await commands.MemberConverter().convert(ctx, user)
                if member in ctx.guild.members:
                    roles_to_remove.append(self.team_manager_cog.get_current_franchise_role(member))
                    removable_roles = []
                    for role in roles_to_remove:
                        if role in member.roles:
                            removable_roles.append(role)
                    await member.remove_roles(*removable_roles)
                    await member.add_roles(former_player_role)
                    await member.edit(nick=(self.team_manager_cog.get_player_nickname(member)))
                    empty = False
            except:
                if notFound == 0:
                    message += "Couldn't find:\n"
                message += "{0}\n".format(user)
                notFound += 1
        if empty:
            message += ":x: Nobody was set as a former player."
        else:
           message += ":white_check_mark: everyone that was found from list is now a former player"
        if notFound > 0:
            message += ". {0} user(s) were not found".format(notFound)
        if retired > 0:
            message += ". {0} user(s) have been set as former players.".format(retired)
        await ctx.send(message)

    @commands.command()
    @commands.guild_only()
    async def getId(self, ctx, *userList):
        """Gets the id for any user that can be found from the userList"""
        found = []
        notFound = []
        for user in userList:
            try:
                member = await commands.MemberConverter().convert(ctx, user)
                if member in ctx.guild.members:
                    nickname = self.get_player_nickname(member)
                    found.append("{1}:{0.name}#{0.discriminator}:{0.id}\n".format(member, nickname))
            except:
                notFound.append(user)
                found.append(None)
        
        # Double Check not found (search by nickname without prefix):
        for player in ctx.guild.members:
            player_nick = self.get_player_nickname(player)
            if player_nick in notFound:
                while player_nick in notFound:
                    notFound.remove(player_nick)
                match_indicies = [i for i, x in enumerate(userList) if x == player_nick]
                for match in match_indicies:
                    found[match] = "{1}:{0.name}#{0.discriminator}:{0.id}\n".format(player, player_nick)
        
        if notFound:
            notFoundMessage = ":x: Couldn't find:\n"
            for user in notFound:
                notFoundMessage += "{0}\n".format(user)
            await ctx.send(notFoundMessage)
            
        messages = []
        if found:
            message = ""
            for member_line in found:
                if member_line and len(message + member_line) < 2000:
                    message += member_line
                else:
                    messages.append(message)
                    message = member_line
            messages.append(message)
        for msg in messages:
            if msg:
                await ctx.send("{0}{1}{0}".format("```", msg))

    @commands.command()
    @commands.guild_only()
    async def getIdsWithRole(self, ctx, role: discord.Role, spreadsheet: bool = False):
        """Gets the id for any user that has the given role"""
        messages = []
        message = ""
        if spreadsheet:
            Outputcsv = "./tmp/Ids.csv"
            header = ["Nickname","Name","Id"]
            csvwrite = open(Outputcsv, 'w', newline='', encoding='utf-8')
            w = csv.writer(csvwrite, delimiter=',')
            w.writerow(header)
            for member in role.members:
                nickname = self.get_player_nickname(member)
                newrow = ["{0}".format(nickname), "{0.name}#{0.discriminator}".format(member), "{0.id}".format(member)]
                w.writerow(newrow)
            csvwrite.close()
            await ctx.send("Done", file=File(Outputcsv))
            os.remove(Outputcsv)
        else:
            for member in role.members:
                nickname = self.get_player_nickname(member)
                message += "{1}:{0.name}#{0.discriminator}:{0.id}\n".format(member, nickname)
                if len(message) > 1900:
                    messages.append(message)
                    message = ""
            if message:
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
        
        for member in currentRole.members:
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

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setDEMessage(self, ctx, *, message):
        """Sets the draft eligible message. This message will be sent to anyone who is made a DE via the makeDE command"""
        await self._save_draft_eligible_message(ctx, message)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def getDEMessage(self, ctx):
        """Gets the draft eligible message"""
        try:
            await ctx.send("Draft eligible message set to: {0}".format((await self._draft_eligible_message(ctx))))
        except:
            await ctx.send(":x: Draft eligible message not set")


    def get_player_nickname(self, user: discord.Member):
        if user.nick:
            array = user.nick.split(' | ', 1)
            if len(array) == 2:
                currentNickname = array[1].strip()
            else:
                currentNickname = array[0]
            return currentNickname
        return user.name
    
    async def _draft_eligible_message(self, ctx):
        return await self.config.guild(ctx.guild).DraftEligibleMessage()

    async def _save_draft_eligible_message(self, ctx, message):
        await self.config.guild(ctx.guild).DraftEligibleMessage.set(message)

    async def _send_member_message(self, ctx, member, message):
        message_title = "**Message from {0}:**\n\n".format(ctx.guild.name)
        command_prefix = ctx.prefix
        message = message.replace('[p]', command_prefix)
        message = message_title + message
        await member.send(message)

