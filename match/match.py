import discord
import re
import ast
import random
from datetime import datetime
from discord.ext import commands

class Match:
    """Used to get the match information"""

    CONFIG_COG = None

    def __init__(self, bot):
        self.bot = bot
        self.CONFIG_COG = self.bot.get_cog("TransactionConfiguration")

    @commands.command(pass_context=True)
    async def clearSchedule(self, ctx):
        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        server_dict['schedule'] = {}
        self.CONFIG_COG.save_data()
        await self.bot.say("Done.")

    @commands.command(pass_context=True)
    async def match(self, ctx, *args):
        """Get match info.

        If no arguments are provided, retrieve the match info for the match day set
        at the server level for the requesting user's team. This will fail if the
        user has no team role or if the match day is not set.
        
        If one argument is provided, it must be the match day to retrieve. If more
        than one argument is provided, the first must be the match day followed by
        a list of teams for which the match info should be retrieved.

        Example: `!match 1 derechos "killer bees"`
        """
        matchDay = args[0] if len(args) > 0 else self._currentMatchDay(ctx)
        # TODO: make this work based on the user's roles
        teams = args[1:] if len(args) > 1 else []
        for team in teams:
            teamRole = self._roleForTeamName(ctx, team)
            if not teamRole:
                await self.bot.say(":x: Could not find team \"{0}\"".format(team))
                return
            matchIndex = self._teamDayMatchIndex(ctx, teamRole.id, matchDay)
            if matchIndex is not None:
                await self.bot.say(self._formatMatchInfo(ctx, matchIndex))
            else:
                await self.bot.say("No match on day {0} for {1}".format(matchDay, teamRole.name))

    @commands.command(pass_context=True)
    async def addMatches(self, ctx, *matches):
        """Add the matches provided to the schedule.

        Arguments:
            matches -- One or more matches in the following format:
                "['<matchDay>','<matchDate>','<home>','<away>','<roomName>','<roomPassword>']"
                Each match should be separated by a space. Also, matchDate should be
                formatted like with the full month name, day of month and 4-digit year.
                The room name and password are optional. They will be generated if absent.
                Note that the placment of the double versus single quotes is important, as
                is the comma after the day of month.

            Examples:
            ```
                [p]addMatches "['1','September 10, 2018','Fire Ants','Leopards','octane','worst car']"
                [p]addMatches "['1','September 10, 2018','Fire Ants','Leopards']"
            ```
        """
        try:
            for matchStr in matches:
                match = ast.literal_eval(matchStr)
                await self.bot.say("Adding match: " + repr(match))
                await self.addMatch(ctx, *match)
        except:
            await self.bot.say(":x: Error trying to add matches.")
            raise

    @commands.command(pass_context=True)
    async def teamList(self, ctx, teamName : str):
        teamRole = self._roleForTeamName(ctx, teamName)
        if teamRole is None:
            await self.bot.say(":x: Could not match {0} to a role".format(teamName))
            return
        await self.bot.say(self._formatTeamInfo(ctx, teamRole))
        return

    @commands.command(pass_context=True)
    async def setMatchDay(self, ctx, day : int):
        """Sets the match day to the specified day. This match day is used when accessing the info in the !match command"""
        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        
        try:
            server_dict.setdefault('Match Day', day)
            self.CONFIG_COG.save_data()
            await self.bot.say("Done")
        except:
            await self.bot.say(":x: Error trying to set the match day. Make sure that the transaction configuration cog is loaded")

    @commands.command(pass_context=True)
    async def getMatchDay(self, ctx):
        """Gets the transaction-log channel"""
        try:
            await self.bot.say("Match day set to: {0}".format(self._currentMatchDay(ctx)))
        except:
            await self.bot.say(":x: Match day not set")

    @commands.command(pass_context=True)
    async def addMatch(self, ctx, matchDay, matchDate, home, away, *args):
        """Adds a single match to the schedule.
        
        Arguments:
            ctx -- the bot context
            matchDay -- the matchDay to add the match to
            matchDate -- the date the match should be played
            home -- the home team (must match the role name)
            away -- the away team (must match the role name)
            roomName -- (optional) the name for the RL match lobby, Autogenerated if not provided.
            roomPass -- (optional) the password for the match lobby. Autogenerated if not provided. 
        Note: Any "extra" arguments are ignored.
        """

        # TODO: 
        #       Other validation
        #           - matchDay is a number
        #           - that there aren't extra args

        # Process inputs to normalize the data (e.g. convert team names to roles)
        matchDateError = None
        try:
            datetime.strptime(matchDate, '%B %d, %Y').date()
        except Exception as err:
            matchDateError = "Date not valid: {0}".format(err)
        homeRole = self._roleForTeamName(ctx, home)
        awayRole = self._roleForTeamName(ctx, away)
        roomName = args[0] if len(args) > 0 else self._generateNamePass()
        roomPass = args[1] if len(args) > 1 else self._generateNamePass()

        # Validation of input
        errors = []
        if matchDateError:
            errors.append("Date provided is not valid. (Make sure to use the right format.)")
        if not homeRole:
            errors.append("Home team role not found.")
        if not awayRole:
            errors.append("Away team role not found.")
        if len(errors) > 0:
            await self.bot.say(":x: Errors with input:\n\n  * {0}\n".format("\n  * ".join(errors)))
            return
        
        # Schedule "schema" in pseudo-JSON style:
        # "schedule": {
        #   "matches": [ <list of all matches> ],
        #   "teamDays": { <dict where keys are tuples of team role names and
        #                 match days with list of indexes of all matches> }
        # }

        # Check for pre-existing matches
        homeMatchIndex = self._teamDayMatchIndex(ctx, homeRole.id, matchDay)
        awayMatchIndex = self._teamDayMatchIndex(ctx, awayRole.id, matchDay)
        errors = []
        if homeMatchIndex is not None:
            errors.append("Home team already has a match for match day {0}".format(matchDay))
        if awayMatchIndex is not None:
            errors.append("Away team already has a match for match day {0}".format(matchDay))
        if len(errors) > 0:
            await self.bot.say(":x: Could not create match:\n\n  * {0}\n".format("\n  * ".join(errors)))
            return

        matchData = {
            'matchDay': matchDay,
            'matchDate': matchDate,
            'home': homeRole.id,
            'away': awayRole.id,
            'roomName': roomName,
            'roomPass': roomPass
        }

        try:
            # Append new match and create an index in "teamDays" for both teams.
            server_dict = self.CONFIG_COG.get_server_dict(ctx)
            allMatches = server_dict.setdefault('schedule', {}).setdefault('matches', [])
            teamDays = server_dict.setdefault('teamDays', {})
            teamDays[self._keyForTeamDay(homeRole.id, matchDay)] = len(allMatches)
            teamDays[self._keyForTeamDay(awayRole.id, matchDay)] = len(allMatches)
            allMatches.append(matchData)
            self.CONFIG_COG.save_data()

            # Tell the user we are done.
            message = "Match saved for: \n"
            message += "  Match day: {0} ({1})\n".format(matchDay, matchDate)
            message += "  Home team: {0}\n".format(homeRole.name)
            message += "  Away team: {0}\n".format(awayRole.name)
            message += "  Room name/pass: {0}/{1}".format(roomName, roomPass)
            await self.bot.say(message)
        except Exception as err:
            await self.bot.say(":x: Error trying to add match data. Make sure the transactionConfiguration cog is loaded.")
            await self.bot.say("Error was: {0}".format(err))

    def _currentMatchDay(self, ctx):
        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        return server_dict["Match Day"]

    def _teamDayMatchIndex(self, ctx, teamRoleId, matchDay):
        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        teamDays = server_dict.setdefault('teamDays', {})
        return teamDays.get(self._keyForTeamDay(teamRoleId, matchDay))

    def _keyForTeamDay(self, teamRoleId, matchDay):
        return "{0}|{1}".format(teamRoleId, matchDay)

    def _roleForTeamName(self, ctx, teamName):
        """ Retrieve the matching role for the provided team name. Returns None if there is no match."""
        roles = ctx.message.server.roles
        for role in roles:
            # Do we want `startswith` here? Leaving it as it is what was used before
            if role.name.lower().startswith(teamName.lower()):
                return role
        return None
    
    def _gmAndMembersFromTeamRole(self, ctx, teamRole):
        gm = None
        teamMembers = []
        for member in ctx.message.server.members:
            if teamRole in member.roles:
                if self.CONFIG_COG.find_role_by_name(member.roles, "General Manager") is not None:
                    gm = member
                else:
                    teamMembers.append(member)
        return (gm, teamMembers)

    def _formatTeamMemberForMessage(self, member, *args):
        extraRoles = list(args)

        name = member.nick if member.nick else member.name
        if self.CONFIG_COG.find_role_by_name(member.roles, "Captain") is not None:
            extraRoles.append("C")
        roleString = "" if len(extraRoles) == 0 else " ({0})".format("|".join(extraRoles))
        return "{0}{1}".format(name, roleString)

    def _formatMatchInfo(self, ctx, matchIndex):
        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        match = server_dict.setdefault('schedule', {}).setdefault('matches', [])[matchIndex]
        # Match format:
        # matchData = {
        #     'matchDay': matchDay,
        #     'matchDate': matchDate,
        #     'home': homeRole.id,
        #     'away': awayRole.id,
        #     'roomName': roomName,
        #     'roomPass': roomPass
        # }
        roles = ctx.message.server.roles
        home = self.CONFIG_COG.find_role(roles, match['home'])
        away = self.CONFIG_COG.find_role(roles, match['away'])
        message = "__Match Day {0}: {1}__\n".format(match['matchDay'], match['matchDate'])
        message += "**{0}**\n    versus\n**{1}**\n\n".format(home.name, away.name)
        message += "Room Name: **{0}**\nPassword: **{1}**".format(match['roomName'], match['roomPass'])
        # TODO: Add other info (complaint form, disallowed maps, enable crossplay, etc.)
        message += "\n\n*Other info here*\n\n"
        message += "**Home Team:**\n"
        message += self._formatTeamInfo(ctx, home)
        message += "\n**Away Team:**\n"
        message += self._formatTeamInfo(ctx, away)

        return message

    def _formatTeamInfo(self, ctx, teamRole):
        gm, teamMembers = self._gmAndMembersFromTeamRole(ctx, teamRole)
        
        message = "```\n{0}:\n".format(teamRole.name)
        if gm:
            message += "  {0}\n".format(self._formatTeamMemberForMessage(gm, "GM"))
        for member in teamMembers:
            message += "  {0}\n".format(self._formatTeamMemberForMessage(member))
        message += "```\n"
        return message
    
    def _generateNamePass(self):
        # TODO: Load from file?
        set = [
            'octane', 'takumi', 'dominus', 'hotshot', 'batmobile', 'mantis',
            'paladin', 'twinmill', 'centio', 'breakout', 'animus', 'venom',
            'xdevil', 'endo', 'masamune', 'merc', 'backfire', 'gizmo',
            'roadhog', 'armadillo', 'hogsticker', 'luigi', 'mario', 'samus',
            'sweettooth', 'cyclone', 'imperator', 'jager', 'mantis', 'nimbus', 
            'samurai', 'twinzer', 'werewolf', 'maverick', 'artemis', 'charger',
            'skyline', 'aftershock', 'boneshaker', 'delorean', 'esper',
            'fast4wd', 'gazella', 'grog', 'jeep', 'marauder', 'mclaren',
            'mr11', 'proteus', 'ripper', 'scarab', 'tumbler', 'triton',
            'vulcan', 'zippy',

            'aquadome', 'beckwith', 'champions', 'dfh', 'mannfield',
            'neotokyo', 'saltyshores', 'starbase', 'urban', 'utopia',
            'wasteland', 'farmstead', 'arctagon', 'badlands', 'core707',
            'dunkhouse', 'throwback', 'underpass', 'badlands',

            '20xx', 'biomass', 'bubbly', 'chameleon', 'dissolver', 'heatwave',
            'hexed', 'labyrinth', 'parallaz', 'slipstream', 'spectre',
            'stormwatch', 'tora', 'trigon', 'wetpaint',

            'ara51', 'ballacarra', 'chrono', 'clockwork', 'cruxe',
            'discotheque', 'draco', 'dynamo', 'equalizer', 'gernot', 'hikari',
            'hypnotik','illuminata','infinium', 'kalos', 'lobo', 'looper',
            'photon', 'pulsus', 'raijin', 'reactor', 'roulette', 'turbine',
            'voltaic', 'wonderment', 'zomba',

            'unranked', 'prospect', 'challenger', 'risingstar', 'allstar',
            'superstar', 'champion', 'grandchamp', 'bronze', 'silver', 'gold',
            'platinum', 'diamond',

            'dropshot', 'hoops', 'soccar', 'rumble', 'snowday', 'solo',
            'doubles', 'standard', 'chaos',

            'armstrong', 'bandit', 'beast', 'boomer', 'buzz', 'cblock',
            'casper', 'caveman', 'centice', 'chipper', 'cougar', 'dude',
            'foamer', 'fury', 'gerwin', 'goose', 'heater', 'hollywood',
            'hound', 'iceman', 'imp', 'jester', 'junker', 'khan', 'marley',
            'maverick', 'merlin', 'middy', 'mountain', 'myrtle', 'outlaw', 
            'poncho', 'rainmaker', 'raja', 'rex', 'roundhouse', 'sabretooth',
            'saltie', 'samara', 'scout', 'shepard', 'slider', 'squall',
            'sticks', 'stinger', 'storm', 'sultan', 'sundown', 'swabbie',
            'tex', 'tusk', 'viper', 'wolfman', 'yuri'
        ]
        return set[random.randrange(len(set))]

def setup(bot):
    bot.add_cog(Match(bot))