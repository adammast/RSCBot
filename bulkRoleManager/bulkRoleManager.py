import csv
import os

import discord
from discord import File
from discord.ext.commands import Context
from redbot.core import Config, checks, commands
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate
from teamManager import TeamManager

defaults = {"DraftEligibleMessage": None}

class BulkRoleManager(commands.Cog):
    """Used to manage roles role for large numbers of members"""
    
    PERM_FA_ROLE = "PermFA"

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567897, force_registration=True)
        self.config.register_guild(**defaults)
        self.team_manager_cog: TeamManager = bot.get_cog("TeamManager")

#region commands

    @commands.command()
    @commands.guild_only()
    async def getAllWithRole(self, ctx: Context, role: discord.Role, get_nickname = False):
        """Prints out a list of members with the specific role"""
        count = 0
        messages = []
        message = ""
        await ctx.send("Players with {0} role:\n".format(role.name))
        for member in role.members:
            if get_nickname:
                message += "{0.display_name}: {0.name}#{0.discriminator}\n".format(member)
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
    async def removeRoleFromAll(self, ctx: Context, role: discord.Role):
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
    async def addRole(self, ctx: Context, role : discord.Role, *user_list):
        """Adds the role to every member that can be found from the user list"""
        empty = True
        added = 0
        had = 0
        not_found = 0
        message = ""
        for user in user_list:
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
                if not_found == 0:
                    message += "Couldn't find:\n"
                message += "{0}\n".format(user)
                not_found += 1
        if empty:
            message += ":x: Nobody was given the role {0}".format(role.name)
        else:
           message += ":white_check_mark: {0} role given to everyone that was found from list".format(role.name)
        if not_found > 0:
            message += ". {0} user(s) were not found".format(not_found)
        if had > 0:
            message += ". {0} user(s) already had the role".format(had)
        if added > 0:
            message += ". {0} user(s) had the role added to them".format(added)
        await ctx.send(message)

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def removeRole(self, ctx: Context, role : discord.Role, *user_list):
        """Removes the role from every member that can be found from the user list"""
        empty = True
        removed = 0
        not_have = 0
        not_found = 0
        message = ""
        for user in user_list:
            try:
                member = await commands.MemberConverter().convert(ctx, user)
                if member in ctx.guild.members:
                    if role in member.roles:
                        await member.remove_roles(role)
                        removed += 1
                    else:
                        not_have += 1
                    empty = False
            except:
                if not_found == 0:
                    message += "Couldn't find:\n"
                message += "{0}\n".format(user)
                not_found += 1
        if empty:
            message += ":x: Nobody had the {0} role removed".format(role.name)
        else:
           message += ":white_check_mark: {0} role removed from everyone that was found from list".format(role.name)
        if not_found > 0:
            message += ". {0} user(s) were not found".format(not_found)
        if not_have > 0:
            message += ". {0} user(s) didn't have the role".format(not_have)
        if removed > 0:
            message += ". {0} user(s) had the role removed".format(removed)
        await ctx.send(message)

    @commands.command(aliases=["addMissingServerRoles"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def addRequiredServerRoles(self, ctx: Context):
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
    async def makeDE(self, ctx: Context, *user_list):
        """Adds the Draft Eligible and League roles, removes Spectator role, and adds the DE prefix to every member that can be found from the user list"""
        empty = True
        added = 0
        had = 0
        not_found = 0
        de_role = None
        league_role = None
        spectator_role = None
        former_player_role = None
        message = ""
        for role in ctx.guild.roles:
            if role.name == "Draft Eligible":
                de_role = role
            elif role.name == "League":
                league_role = role
            elif role.name == "Spectator":
                spectator_role = role
            elif role.name == "Former Player":
                former_player_role = role
            if league_role and de_role and spectator_role and former_player_role:
                break

        if de_role is None or league_role is None or spectator_role is None or former_player_role is None:
            await ctx.send(":x: Couldn't find either the Draft Eligible, League, Spectator, or Former Player role in the server. Use `{0}addRequiredServerRoles` to add these roles.".format(ctx.prefix))
            return

        for user in user_list:
            try:
                member = await commands.MemberConverter().convert(ctx, user)
            except:
                message += "Couldn't find: {0}\n".format(user)
                not_found += 1
                continue
            if member in ctx.guild.members:
                if league_role in member.roles:
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

                await member.add_roles(de_role, league_role)
                added += 1
                await member.edit(nick="{0} | {1}".format("DE", self.get_player_nickname(member)))
                await member.remove_roles(spectator_role, former_player_role)
                deMessage = await self._draft_eligible_message(ctx.guild)
                if deMessage:
                    # await member.send(deMessage)
                    await self.send_member_message(ctx, member, deMessage)
                    
                empty = False
            
        if empty:
            message += ":x: Nobody was given the Draft Eligible role"
        else:
           message += ":white_check_mark: Draft Eligible role given to everyone that was found from list"
        if not_found > 0:
            message += ". {0} user(s) were not found".format(not_found)
        if had > 0:
            message += ". {0} user(s) already had the role or were already in the league".format(had)
        if added > 0:
            message += ". {0} user(s) had the role added to them".format(added)
        await ctx.send(message)
    
    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def makePermFA(self, ctx: Context, tier: str, *user_list):
        """Makes each member that can be found from the user list a permanent Free Agent for the given tier"""
        role_names_to_add = [self.PERM_FA_ROLE, "League", tier, "{0}FA".format(tier)]
        roles_to_add = []
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
        not_found = 0
        had = 0
        added = 0
        message = ""
        for user in user_list:
            try:
                member = await commands.MemberConverter().convert(ctx, user)
            except:
                message += "Couldn't find: {0}\n".format(user)
                not_found += 1
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
                    await self.send_member_message(ctx, member, tier_change_msg)
                
                if self.get_player_nickname(member)[:5] != "FA | ":
                    try:
                        await member.edit(nick="{0} | {1}".format("FA", self.get_player_nickname(member)))
                    except (discord.errors.Forbidden, discord.errors.HTTPException):
                        await ctx.send("Cannot set nickname for {0}".format(member.name))

                await member.add_roles(*roles_to_add)
                added += 1
        
        if len([user_list]) and not empty:
            message = "{0} members processed...\n".format(len([user_list])) + message
        if empty:
            message += ":x: Nobody was set as a {0} permanent FA".format(tier)
        else:
           message += ":white_check_mark: All members found are now {0} permanent FAs.".format(tier)
        if not_found:
            message += ". {0} user(s) were not found".format(not_found)
        if had:
            message += ". {0} user(s) were already in this tier.".format(had)
        if added:
            message += ". {0} user(s) had the role added to them".format(added)
        await ctx.send(message)       

    @commands.command(aliases=["retirePlayer", "retirePlayers", "setFormerPlayer"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def retire(self, ctx: Context, *user_list):
        """Removes league roles and adds 'Former Player' role for every member that can be found from the user list"""
        empty = True
        retired = 0
        not_found = 0
        message = ""
        former_player_str = "Former Player"
        former_player_role = self.team_manager_cog._find_role_by_name(ctx, former_player_str)

        if not former_player_role:
            former_player_role = await self.team_manager_cog.create_role(ctx, former_player_str)

        roles_to_remove = [
            self.team_manager_cog._find_role_by_name(ctx, "Draft Eligible"),
            self.team_manager_cog._find_role_by_name(ctx, "League"),
            self.team_manager_cog._find_role_by_name(ctx, "Free Agent"),
            self.team_manager_cog._find_role_by_name(ctx, self.PERM_FA_ROLE)
        ]
        tiers = await self.team_manager_cog._tiers(ctx.guild)
        for tier in tiers:
            tier_role = self.team_manager_cog._get_tier_role(ctx, tier)
            if tier_role:
                tier_fa_role = self.team_manager_cog._find_role_by_name(ctx, "{0}FA".format(tier))
            roles_to_remove.append(tier_role)
            roles_to_remove.append(tier_fa_role)

        for user in user_list:
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
                if not_found == 0:
                    message += "Couldn't find:\n"
                message += "{0}\n".format(user)
                not_found += 1
        if empty:
            message += ":x: Nobody was set as a former player."
        else:
           message += ":white_check_mark: everyone that was found from list is now a former player"
        if not_found > 0:
            message += ". {0} user(s) were not found".format(not_found)
        if retired > 0:
            message += ". {0} user(s) have been set as former players.".format(retired)
        await ctx.send(message)

    @commands.command()
    @commands.guild_only()
    async def getId(self, ctx: Context, *user_list):
        """Gets the id for any user that can be found from the user list"""
        found = []
        not_found = []
        for user in user_list:
            try:
                member = await commands.MemberConverter().convert(ctx, user)
                if member in ctx.guild.members:
                    nickname = self.get_player_nickname(member)
                    found.append("{1}:{0.name}#{0.discriminator}:{0.id}\n".format(member, nickname))
            except:
                not_found.append(user)
                found.append(None)
        
        # Double Check not found (search by nickname without prefix):
        for player in ctx.guild.members:
            player_nick = self.get_player_nickname(player)
            if player_nick in not_found:
                while player_nick in not_found:
                    not_found.remove(player_nick)
                match_indicies = [i for i, x in enumerate(user_list) if x == player_nick]
                for match in match_indicies:
                    found[match] = "{1}:{0.name}#{0.discriminator}:{0.id}\n".format(player, player_nick)
        
        if not_found:
            not_foundMessage = ":x: Couldn't find:\n"
            for user in not_found:
                not_foundMessage += "{0}\n".format(user)
            await ctx.send(not_foundMessage)
            
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
    async def getIdsWithRole(self, ctx: Context, role: discord.Role, spreadsheet: bool = False):
        """Gets the id for any user that has the given role"""
        messages = []
        message = ""
        if spreadsheet:
            output_csv = "./tmp/Ids.csv"
            header = ["Nickname","Name","Id"]
            csvwrite = open(output_csv, 'w', newline='', encoding='utf-8')
            w = csv.writer(csvwrite, delimiter=',')
            w.writerow(header)
            for member in role.members:
                nickname = self.get_player_nickname(member)
                newrow = ["{0}".format(nickname), "{0.name}#{0.discriminator}".format(member), "{0.id}".format(member)]
                w.writerow(newrow)
            csvwrite.close()
            await ctx.send("Done", file=File(output_csv))
            os.remove(output_csv)
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
    async def giveRoleToAllWithRole(self, ctx: Context, current_role: discord.Role, role_to_give: discord.Role):
        """Gives the role_to_give to every member who already has the current_role"""
        count = 0
        had_role_count = 0
        count_given = 0
        
        for member in current_role.members:
            count += 1
            if role_to_give in member.roles:
                had_role_count += 1
            else:
                await member.add_roles(role_to_give)
                count_given += 1
        if count == 0:
            message = ":x: Nobody has the {0} role".format(current_role.name)
        else:
            message = ":white_check_mark: {0} user(s) had the {1} role".format(count, current_role.name)
            if had_role_count > 0:
                message += ". {0} user(s) already had the {1} role".format(had_role_count, role_to_give.name)
            if count_given > 0:
                message += ". {0} user(s) had the {1} role added to them".format(count_given, role_to_give.name)
        await ctx.send(message)

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setDEMessage(self, ctx: Context, *, message):
        """Sets the draft eligible message. This message will be sent to anyone who is made a DE via the makeDE command"""
        await self._save_draft_eligible_message(ctx.guild, message)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def getDEMessage(self, ctx: Context):
        """Gets the draft eligible message"""
        try:
            await ctx.send("Draft eligible message set to: {0}".format((await self._draft_eligible_message(ctx.guild))))
        except:
            await ctx.send(":x: Draft eligible message not set")

#endregion

#region helper methods

    def get_player_nickname(self, member: discord.Member):
        if member.nick:
            array = member.nick.split(' | ', 1)
            if len(array) == 2:
                currentNickname = array[1].strip()
            else:
                currentNickname = array[0]
            return currentNickname
        return member.name

    async def send_member_message(self, ctx: Context, member: discord.Member, message):
        message_title = "**Message from {0}:**\n\n".format(ctx.guild.name)
        command_prefix = ctx.prefix
        message = message.replace('[p]', command_prefix)
        message = message_title + message
        await member.send(message)

#endregion

#region load/save methods
    
    async def _draft_eligible_message(self, guild: discord.Guild):
        return await self.config.guild(guild).DraftEligibleMessage()

    async def _save_draft_eligible_message(self, guild: discord.Guild, message):
        await self.config.guild(guild).DraftEligibleMessage.set(message)

#endregion
