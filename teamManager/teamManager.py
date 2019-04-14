import discord
import re

from discord.ext import commands


class TeamManager:
    """Used to get the match information"""

    DATASET = "TeamData"
    TIERS_KEY = "Tiers"
    TEAMS_KEY = "Teams"
    TEAM_ROLES_KEY = "Team Roles"
    FRANCHISE_ROLE_KEY = "Franchise Role"
    TIER_ROLE_KEY = "Tier Role"
    GM_ROLE = "General Manager"
    CAPTAN_ROLE = "Captain"

    def __init__(self, bot):
        self.bot = bot
        self.data_cog = self.bot.get_cog("RscData")

    # @commands.command(pass_context=True, no_pm=True)
    # async def teamList(self, ctx, teamName: str):
    #     team_role = self.team_for_name(ctx, teamName)
    #     if team_role is None:
    #         await self.bot.say(
    #             ":x: Could not match {0} to a role".format(teamName))
    #         return
    #     await self.bot.say(self.format_team_info(ctx, team_role))
    #     return

    @commands.command(pass_context=True, no_pm=True)
    async def tierList(self, ctx):
        tiers = self._tiers(ctx)
        if tiers:
            await self.bot.say(
                "Tiers set up in this server: {0}".format(", ".join(tiers)))
        else:
            await self.bot.say("No tiers set up in this server.")

    @commands.command(pass_context=True, no_pm=True)
    async def addTier(self, ctx, tier_name: str):
        tiers = self._tiers(ctx)
        tiers.append(tier_name)
        self._save_tiers(ctx, tiers)
        await self.bot.say("Done.")

    @commands.command(pass_context=True, no_pm=True)
    async def removeTier(self, ctx, tier_name: str):
        tiers = self._tiers(ctx)
        try:
            tiers.remove(tier_name)
        except ValueError:
            await self.bot.say(
                "{0} does not seem to be a tier.".format(tier_name))
            return
        self._save_tiers(ctx, tiers)
        await self.bot.say("Done.")

    @commands.command(pass_context=True, no_pm=True)
    async def teamList(self, ctx):
        teams = self._teams(ctx)
        if teams:
            await self.bot.say(
                "Teams set up in this server: {0}".format(", ".join(teams)))
        else:
            await self.bot.say("No teams set up in this server.")

    @commands.command(pass_context=True, no_pm=True)
    async def teamRoles(self, ctx, team_name: str):
        teams = self._teams(ctx)
        if teams:
            if team_name in teams:
                team_roles = self._team_roles(ctx)
                team_data = team_roles.setdefault(team_name, {})
                franchise_role_id = team_data["Franchise Role"]
                tier_role_id = team_data["Tier Role"]
                franchise_role = self.find_role(ctx, franchise_role_id)
                tier_role = self.find_role(ctx, tier_role_id)
                if franchise_role and tier_role:
                    await self.bot.say(
                        "Franchise role for {0} = {1}\nTier role for {0} = {2}".format(team_name, franchise_role.name, tier_role.name))
            else:
                await self.bot.say(
                    "{0} not found in team list.".format(team_name))
        else:
            await self.bot.say("No teams set up in this server.")

    @commands.command(pass_context=True, no_pm=True)
    async def addTeam(self, ctx, team_name: str, franchise_role: discord.Role, tier: discord.Role):
        teams = self._teams(ctx)
        teams.append(team_name)
        team_roles = self._team_roles(ctx)
        team_data = team_roles.setdefault(team_name, {})
        team_data["Franchise Role"] = franchise_role.id
        team_data["Tier Role"] = tier.id
        self._save_teams(ctx, teams)
        self._save_team_roles(ctx, team_roles)
        await self.bot.say("Done.")

    @commands.command(pass_context=True, no_pm=True)
    async def removeTeam(self, ctx, team_name: str):
        teams = self._teams(ctx)
        try:
            teams.remove(team_name)
        except ValueError:
            await self.bot.say(
                "{0} does not seem to be a team.".format(team_name))
            return
        self._save_teams(ctx, teams)
        await self.bot.say("Done.")

    def is_gm(self, member):
        for role in member.roles:
            if role.name == self.GM_ROLE:
                return True
        return False

    def is_captain(self, member):
        for role in member.roles:
            if role.name == self.CAPTAN_ROLE:
                return True
        return False

    # def teams_for_user(self, ctx, user):
    #     tiers = self._tiers(ctx)
    #     team_roles = []
    #     for role in user.roles:
    #         tier = self._extract_tier_from_role(role)
    #         if tier is not None:
    #             if tier in tiers:
    #                 team_roles.append(role)
    #     return team_roles

    # def teams_for_names(self, ctx, *team_names):
    #     """Retrieve the matching team roles for the provided names.

    #     Names with no matching roles are skipped. If none are found, an empty
    #     list is returned.
    #     """
    #     teams = []
    #     for team_name in team_names:
    #         team = self.team_for_name(ctx, team_name)
    #         if team:
    #             teams.append(team)
    #     return teams

    # def team_for_name(self, ctx, team_name):
    #     """ Retrieve the matching team role for the provided name.

    #     Returns None if there is no match.
    #     """
    #     roles = ctx.message.server.roles
    #     for role in roles:
    #         # Do we want `startswith` here? Leaving it as it is what was
    #         # used before
    #         if role.name.lower().startswith(team_name.lower()):
    #             return role
    #     return None

    # def gm_and_members_from_team(self, ctx, team_role):
    #     """Retrieve tuple with the gm user and a list of other users that are
    #     on the team indicated by the provided team_role.
    #     """
    #     gm = None
    #     team_members = []
    #     for member in ctx.message.server.members:
    #         if team_role in member.roles:
    #             if self.is_gm(member):
    #                 gm = member
    #             else:
    #                 team_members.append(member)
    #     return (gm, team_members)

    # def format_team_info(self, ctx, team_role):
    #     gm, team_members = self.gm_and_members_from_team(ctx, team_role)

    #     message = "```\n{0}:\n".format(team_role.name)
    #     if gm:
    #         message += "  {0}\n".format(
    #             self._format_team_member_for_message(gm, "GM"))
    #     for member in team_members:
    #         message += "  {0}\n".format(
    #             self._format_team_member_for_message(member))
    #     if not team_members:
    #         message += "  No known members."
    #     message += "```\n"
    #     return message

    def _format_team_member_for_message(self, member, *args):
        extraRoles = list(args)

        name = member.nick if member.nick else member.name
        if self.is_captain(member):
            extraRoles.append("C")
        roleString = ""
        if extraRoles:
            roleString = " ({0})".format("|".join(extraRoles))
        return "{0}{1}".format(name, roleString)

    def _all_data(self, ctx):
        all_data = self.data_cog.load(ctx, self.DATASET)
        return all_data

    def _tiers(self, ctx):
        all_data = self._all_data(ctx)
        tiers = all_data.setdefault(self.TIERS_KEY, [])
        return tiers

    def _save_tiers(self, ctx, tiers):
        all_data = self._all_data(ctx)
        all_data[self.TIERS_KEY] = tiers
        self.data_cog.save(ctx, self.DATASET, all_data)

    def _extract_tier_from_role(self, team_role):
        tier_matches = re.findall(r'\w*\b(?=\))', team_role.name)
        return None if not tier_matches else tier_matches[0]

    def _teams(self, ctx):
        all_data = self._all_data(ctx)
        teams = all_data.setdefault(self.TEAMS_KEY, [])
        return teams

    def _save_teams(self, ctx, teams):
        all_data = self._all_data(ctx)
        all_data[self.TEAMS_KEY] = teams
        self.data_cog.save(ctx, self.DATASET, all_data)

    def _team_roles(self, ctx):
        all_data = self._all_data(ctx)
        team_roles = all_data.setdefault(self.TEAM_ROLES_KEY, {})
        return team_roles

    def _save_team_roles(self, ctx, team_roles):
        all_data = self._all_data(ctx)
        all_data[self.TEAM_ROLES_KEY] = team_roles
        self.data_cog.save(ctx, self.DATASET, all_data)

    def find_role(self, ctx, role_id):
        server = ctx.message.server
        roles = server.roles
        for role in roles:
            if role.id == role_id:
                return role
        raise LookupError('No role with id: {0} found in server roles'.format(role_id))

    def log_info(self, message):
        self.data_cog.logger().info("[TeamManager] " + message)

    def log_error(self, message):
        self.data_cog.logger().error("[TeamManager] " + message)


def setup(bot):
    bot.add_cog(TeamManager(bot))
