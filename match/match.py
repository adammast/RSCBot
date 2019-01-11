import traceback
import re
import ast
import random
from datetime import datetime
import json

import discord
from discord.ext import commands

class Match:
    """Used to get the match information"""

    CONFIG_COG = None

    def __init__(self, bot):
        self.bot = bot
        self.CONFIG_COG = self.bot.get_cog("TransactionConfiguration")
        self.data = None

    @commands.command(pass_context=True)
    async def printScheduleData(self, ctx):
        """Print all raw schedule data.
        
        Note: In the real server, this will likely fail just due to the amount 
        of data. Intended for use in debugging on test servers. Basically,
        when there are only a handful of matches total.
        
        TODO: Might even comment this out in prod.
        """
        self.getData(ctx)
        dump = json.dumps(self.schedule(ctx), indent=4, sort_keys=True)
        await self.bot.say("Here is all of the schedule data in "
                           "JSON format.\n```json\n{0}\n```".format(dump))

    @commands.command(pass_context=True)
    async def clearSchedule(self, ctx):
        """Clear all scheduled matches."""
        self.getData(ctx)
        self.schedule(ctx).clear()
        self.saveData()
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

        Note: If no team names are sent, GMs (or anyone with multiple team roles)
        will get matchups for all their teams. User's without a team role will get
        nothing.
        """
        self.getData(ctx)
        matchDay = args[0] if len(args) > 0 else self._currentMatchDay(ctx)
        teamNamesProvided = len(args) > 1
        userTeamRoles = self._teamRolesForUser(ctx, ctx.message.author)
        teamRoles = await self._rolesForTeamNames(ctx, *args[1:]) if teamNamesProvided else userTeamRoles
        teamRoleForInfo = userTeamRoles[0] if len(userTeamRoles) > 0 and not teamNamesProvided else None

        if len(teamRoles) == 0:
            await self.bot.say("No team roles found. If you provided teams, "
                               "check the spelling. If not, you do not have "
                               "a team role.")
            return

        for teamRole in teamRoles:
            matchIndex = await self._teamDayMatchIndex(ctx, teamRole.id, matchDay)
            if matchIndex is not None:
                await self.bot.say(self._formatMatchInfo(ctx, matchIndex, teamRoleForInfo))
            else:
                await self.bot.say("No match on day {0} for {1}".format(matchDay, teamRole.name))

    @commands.command(pass_context=True)
    async def addMatches(self, ctx, *matches):
        """Add the matches provided to the schedule.

        Arguments:
            matches -- One or more matches in the following format:
                "['<matchDay>','<matchDate>','<home>','<away>','<roomName>','<roomPassword>']"
                Each match should be separated by a space. Also, matchDate should be
                formatted with the full month name, day of month and 4-digit year.
                The room name and password are optional. They will be generated if absent.
                Note that the placment of the double versus single quotes is important, as
                is the comma after the day of month.

            Examples:
            ```
                [p]addMatches "['1','September 10, 2018','Fire Ants','Leopards','octane','worst car']"
                [p]addMatches "['1','September 10, 2018','Fire Ants','Leopards']" "['2','September 13, 2018','Leopards','Fire Ants']"
            ```
        """
        self.getData(ctx)
        addedCount = 0
        for matchStr in matches:
            match = ast.literal_eval(matchStr)
            await self.bot.say("Adding match: {0}".format(repr(match)))
            await self._addMatch(ctx, *match)
            addedCount += 1
        try:
            self.saveData()
            await self.bot.say("Added {0} match(es).".format(addedCount))
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
        """Sets the match day to the specified day.
        
        This match day is used when accessing the info in the !match command.
        """
        self.getData(ctx)
        self.data.setdefault("Match Day", day)
        try:
            self.saveData()
            await self.bot.say("Done")
        except:
            await self.bot.say(":x: Error trying to set the match day. Make "
                               "sure that the transaction configuration cog "
                               "is loaded")

    @commands.command(pass_context=True)
    async def getMatchDay(self, ctx):
        """Gets the transaction-log channel"""
        self.getData(ctx)
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
            roomName -- (optional) the name for the RL match lobby,
                        Autogenerated if not provided.
            roomPass -- (optional) the password for the match lobby.
                        Autogenerated if not provided. 
        Note: Any "extra" arguments are ignored.
        """
        self.getData(ctx)
        match = await self._addMatch(ctx, matchDay, matchDate, home, away, *args)
        if match:
            message = "Saving match for: \n"
            message += "  Match day: {0} ({1})\n".format(match['matchDay'], match['matchDate'])
            message += "  Home team: {0}\n".format(match['home'])
            message += "  Away team: {0}\n".format(match['away'])
            message += "  Room name/pass: {0}/{1}".format(match['roomName'], match['roomPass'])
            await self.bot.say(message)
        try:
            self.saveData()
            await self.bot.say("Done")
        except Exception as err:
            await self.bot.say(":x: Error trying to add match data. Make sure "
                               "the transactionConfiguration cog is loaded.")
            await self.bot.say("Error was: {0}".format(err))
            await self.bot.say("Error info: {0}".format(traceback.format_exc()))

    async def _addMatch(self, ctx, matchDay, matchDate, home, away, *args):
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
        # There are other validations we could do, but don't
        #     - matchDay is a number
        #     - that there aren't extra args
        errors = []
        if matchDateError:
            errors.append("Date provided is not valid. "
                          "(Make sure to use the right format.)")
        if not homeRole:
            errors.append("Home team role not found.")
        if not awayRole:
            errors.append("Away team role not found.")
        if len(errors) > 0:
            await self.bot.say(":x: Errors with input:\n\n  "
                               "* {0}\n".format("\n  * ".join(errors)))
            return
        
        # Schedule "schema" in pseudo-JSON style:
        # "schedule": {
        #   "matches": [ <list of all matches> ],
        #   "teamDays": { <dict where keys are tuples of team role names and
        #                 match days with list of indexes of all matches> }
        # }

        # Check for pre-existing matches
        homeMatchIndex = await self._teamDayMatchIndex(ctx, homeRole.id, matchDay)
        awayMatchIndex = await self._teamDayMatchIndex(ctx, awayRole.id, matchDay)
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

        # Append new match and create an index in "teamDays" for both teams.
        allMatches = self.getAllMatches(ctx)
        teamDays = self.getTeamDays(ctx)
        teamDays[self._keyForTeamDay(homeRole.id, matchDay)] = len(allMatches)
        teamDays[self._keyForTeamDay(awayRole.id, matchDay)] = len(allMatches)
        await self.bot.say("allMatches before: {0}".format(allMatches))
        allMatches.append(matchData)
        await self.bot.say("allMatches after: {0}".format(self.getAllMatches(ctx)))

        result = matchData.copy()
        result['home'] = homeRole.name
        result['away'] = awayRole.name
        return result

    def getData(self, ctx):
        if self.data is None:
            print("Reloading data.")
            self.data = self.CONFIG_COG.get_server_dict(ctx)
        return self.data

    def saveData(self):
        print("Saving data: {0}".format(self.data))
        self.CONFIG_COG.save_data()
        self.data = None

    def schedule(self, ctx):
        return self.getData(ctx).setdefault('schedule', {})

    def getTeamDays(self, ctx):
        return self.schedule(ctx).setdefault('teamDays', {})

    def getAllMatches(self, ctx):
        return self.schedule(ctx).setdefault('matches', [])

    def _currentMatchDay(self, ctx):
        server_dict = self.CONFIG_COG.get_server_dict(ctx)
        return server_dict["Match Day"]

    async def _teamDayMatchIndex(self, ctx, teamRoleId, matchDay):
        teamDays = self.getTeamDays(ctx)
        await self.bot.say("teamDays: {0}".format(teamDays))
        result = teamDays.get(self._keyForTeamDay(teamRoleId, matchDay))
        await self.bot.say("teamDayMatchIndex: {0}".format(result))
        return result

    def _keyForTeamDay(self, teamRoleId, matchDay):
        return "{0}|{1}".format(teamRoleId, matchDay)

    async def _rolesForTeamNames(self, ctx, *teamNames):
        """Retrieve the matching roles for the provided team names.
        
        Names with no matching roles are skipped. If none are found, an empty
        list is returned.
        """
        roles = []
        for teamName in teamNames:
            role = self._roleForTeamName(ctx, teamName)
            if role:
                roles.append(role)
            else:
                await self.bot.say('Team not found: "{0}"'.format(teamName))
        return roles

    def _roleForTeamName(self, ctx, teamName):
        """ Retrieve the matching role for the provided team name.
        
        Returns None if there is no match.
        """
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

    def _formatMatchInfo(self, ctx, matchIndex, userTeamRole=None):
        allMatches = self.getAllMatches(ctx)
        match = allMatches[matchIndex]
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
        message += "Room Name: **{0}**\nPassword: **{1}**\n".format(match['roomName'], match['roomPass'])
        if userTeamRole and userTeamRole == home:
            message += ("\nYou are the **home** team. You will create the room "
                        "using the above information. Contact the other team "
                        "when your team is ready to begin the match. Do not "
                        "join a team until the away team starts to.\n"
                        "Remember to ask before the match begins if the other "
                        "team would like to switch server region after 2 games.")
        elif userTeamRole and userTeamRole == away:
            message += ("\nYou are the **away** team. You will join the room using "
                       "the above information once the other team contacts "
                       "you. Do not begin joining a team until your entire "
                       "team is ready to begin playing.")
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

    def _teamRolesForUser(self, ctx, user):
        tierList = self.CONFIG_COG.get_tier_list(ctx)
        teamRoles = []
        for role in user.roles:
            tierName = self._extractTierFromTeamRole(role)
            if tierName is not None:
                if tierName in tierList:
                    teamRoles.append(role)
        return teamRoles

    def _extractTierFromTeamRole(self, teamRole):
        try:
            return re.findall(r'\w*\b(?=\))', teamRole.name)[0]
        except:
            return None


    
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
            'hexed', 'labyrinth', 'parallax', 'slipstream', 'spectre',
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