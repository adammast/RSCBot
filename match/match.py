import traceback
import ast
import random
from datetime import datetime
import json
import discord

from redbot.core import Config
from redbot.core import commands
from redbot.core import checks

defaults = {"MatchDay": 0, "Schedule": {}}

class Match(commands.Cog):
    """Used to get the match information"""

    MATCHES_KEY = "Matches"
    TEAM_DAY_INDEX_KEY = "TeamDays"

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567893, force_registration=True)
        self.config.register_guild(**defaults)
        self.team_manager = bot.get_cog("TeamManager")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def setMatchDay(self, ctx, day: str):
        """Sets the active match day to the specified day.

        This match day is used when accessing the info in the !match command.
        """
        await self._save_match_day(ctx, str(day))
        await ctx.send("Done")

    @commands.command()
    @commands.guild_only()
    async def getMatchDay(self, ctx):
        """Gets the currently active match day."""
        match_day = await self._match_day(ctx)
        if match_day:
            await ctx.send(
                "Current match day is: {0}".format(match_day))
        else:
            await ctx.send(":x: Match day not set. Set with setMatchDay "
                               "command.")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def printScheduleData(self, ctx):
        """Print all raw schedule data.

        Note: In the real server, this will likely fail just due to the amount
        of data. Intended for use in debugging on test servers. Basically,
        when there are only a handful of matches total.

        TODO: Might even comment this out in prod.
        """
        schedule = await self._schedule(ctx)
        dump = json.dumps(schedule, indent=4, sort_keys=True)
        await ctx.send("Here is all of the schedule data in "
                           "JSON format.\n```json\n{0}\n```".format(dump))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearSchedule(self, ctx):
        """Clear all scheduled matches."""
        await self._save_schedule(ctx, {})
        await ctx.send("Done.")

    @commands.command()
    @commands.guild_only()
    async def match(self, ctx, *args):
        """Get match info.

        If no arguments are provided, retrieve the match info for the
        server's currently active match day for the requesting user's
        team or teams. This will fail if the user has no team role or if
        the match day is not set.

        If one argument is provided, it must be the match day to retrieve. If
        more than one argument is provided, the first must be the match day
        followed by a list of teams for which the match info should be
        retrieved.

        Example: `[p]match 1 derechos "killer bees"`

        Note: If no team names are sent, GMs (or anyone with multiple team
        roles) will get matchups for all their teams. User's without a team
        role will get nothing.
        """
        match_day = args[0] if args else await self._match_day(ctx)
        if not match_day:
            await ctx.send("Match day not provided and not set for "
                               "the server.")
            return
        team_names = []
        user_team_names = await self.team_manager.teams_for_user(
            ctx, ctx.message.author)

        team_names_provided = len(args) > 1
        if team_names_provided:
            team_names = args[1:]
        else:
            team_names = user_team_names

        if not team_names:
            await ctx.send("No teams found. If you provided teams, "
                               "check the spelling. If not, you do not have "
                               "roles corresponding to a team.")
            return

        for team_name in team_names:
            match_index = await self._team_day_match_index(ctx, team_name,
                                                     match_day)
            if match_index is not None:
                if ctx.message.author.is_on_mobile():
                    message = await self._format_match_message(ctx, match_index, team_name)
                    await ctx.message.author.send(message)
                else:
                    embed = await self._format_match_embed(ctx, match_index, team_name)
                    await ctx.message.author.send(embed=embed)
            else:
                await ctx.message.author.send(
                    "No match on day {0} for {1}".format(match_day,
                                                         team_name)
                )
        await ctx.message.delete()

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def addMatches(self, ctx, *matches):
        """Add the matches provided to the schedule.

        Arguments:

        matches -- One or more matches in the following format:

        "['<matchDay>','<matchDate>','<home>','<away>','<roomName>','<roomPassword>']"

        Each match should be separated by a space. Also, matchDate should be
        formatted with the full month name, day of month and 4-digit year.
        The room name and password are optional. They will be generated if
        absent. Note that the placment of the double versus single quotes is
        important, as is the comma after the day of month.

        Examples:

        [p]addMatches "['1','September 10, 2020','Fire Ants','Leopards',
        'octane','worst car']"
        [p]addMatches "['1','September 10, 2018','Fire Ants','Leopards']" "[
        '2','September 13, 2018','Leopards','Fire Ants']"

        """
        addedCount = 0
        try:
            for matchStr in matches:
                match = ast.literal_eval(matchStr)
                resultMatch = await self._add_match(ctx, *match)
                if resultMatch:
                    addedCount += 1
        except Exception as e:
            await ctx.send(e)
        finally:
            await ctx.send("Added {0} match(es).".format(addedCount))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def addMatch(self, ctx, match_day, match_date, home, away, *args):
        """Adds a single match to the schedule.

        Arguments:
            ctx -- the bot context
            match_day -- the match_day to add the match to
            match_date -- the date the match should be played
            home -- the home team (must match the role name)
            away -- the away team (must match the role name)
            roomName -- (optional) the name for the RL match lobby,
                        Autogenerated if not provided.
            roomPass -- (optional) the password for the match lobby.
                        Autogenerated if not provided.
        Note: Any "extra" arguments are ignored.
        """
        match = await self._add_match(ctx, match_day, match_date,
                                      home, away, *args)
        if match:
            await ctx.send("Done")


    async def _add_match(self, ctx, match_day, match_date, home, away, *args):
        """Does the actual work to save match data."""
        # Process inputs to normalize the data (e.g. convert team names to
        # roles)
        match_date_error = None
        try:
            datetime.strptime(match_date, '%B %d, %Y').date()
        except Exception as err:
            match_date_error = "Date not valid: {0}".format(err)
        homeRoles = await self.team_manager._roles_for_team(ctx, home)
        awayRoles = await self.team_manager._roles_for_team(ctx, away)
        roomName = args[0] if args else self._generate_name_pass()
        roomPass = args[1] if len(args) > 1 else self._generate_name_pass()

        # Validation of input
        # There are other validations we could do, but don't
        #     - that there aren't extra args
        errors = []
        if match_date_error:
            errors.append("Date provided is not valid. "
                          "(Make sure to use the right format.)")
        if not homeRoles:
            errors.append("Home team roles not found.")
        if not awayRoles:
            errors.append("Away team roles not found.")
        if errors:
            await ctx.send(":x: Errors with input:\n\n  "
                               "* {0}\n".format("\n  * ".join(errors)))
            return

        # Schedule "schema" in pseudo-JSON style:
        # "schedule": {
        #   "matches": [ <list of all matches> ],
        #   "teamDays": { <dict where keys are tuples of team role names and
        #                 match days with list of indexes of all matches> }
        # }

        # Load the data we will use. Race conditions are possible, but
        # our change will be consistent, it might just override what someone
        # else does if they do it at roughly the same time.
        schedule = await self._schedule(ctx)
        # Check for pre-existing matches
        home_match_index = await self._team_day_match_index(
            ctx, home, match_day)
        away_match_index = await self._team_day_match_index(
            ctx, away, match_day)
        errors = []
        if home_match_index is not None:
            errors.append("Home team already has a match for "
                          "match day {0}".format(match_day))
        if away_match_index is not None:
            errors.append("Away team already has a match for "
                          "match day {0}".format(match_day))
        if errors:
            await ctx.send(":x: Could not create match:\n"
                               "\n  * {0}\n".format("\n  * ".join(errors)))
            return

        match_data = {
            'matchDay': match_day,
            'matchDate': match_date,
            'home': home,
            'away': away,
            'roomName': roomName,
            'roomPass': roomPass,
            'streamDetails': None
        }

        # Append new match and create an index in "teamDays" for both teams.
        matches = schedule.setdefault(self.MATCHES_KEY, [])
        team_days = schedule.setdefault(self.TEAM_DAY_INDEX_KEY, {})

        home_key = self._team_day_key(home, match_day)
        team_days[home_key] = len(matches)

        away_key = self._team_day_key(away, match_day)
        team_days[away_key] = len(matches)

        matches.append(match_data)

        await self._save_schedule(ctx, schedule)

        result = match_data.copy()
        result['home'] = home
        result['away'] = away
        return result

    async def _set_match_on_stream(self, ctx, match_day, team, stream_details):
        matches = await self._matches(ctx)
        for match in matches:
            if match['matchDay'] == match_day and (one_team == match['home'] or one_team == match['away']):
                match['streamDetails'] = stream_details
                #match['time'] = time  # ((could add time param to match))
                await self._save_matches(ctx, matches)
                return True
        return False

    async def _schedule(self, ctx):
        return await self.config.guild(ctx.guild).Schedule()

    async def _save_schedule(self, ctx, schedule):
        await self.config.guild(ctx.guild).Schedule.set(schedule)

    async def _matches(self, ctx):
        schedule = await self._schedule(ctx)
        return schedule.setdefault(self.MATCHES_KEY, {})

    async def _save_matches(self, ctx, matches):
        schedule = await self._schedule(ctx)
        schedule[self.MATCHES_KEY] = matches
        await self._save_schedule(ctx, schedule)

    async def _team_days_index(self, ctx):
        schedule = await self._schedule(ctx)
        return schedule.setdefault(self.TEAM_DAY_INDEX_KEY, {})

    async def _save_team_days_index(self, ctx, team_days_index):
        schedule = await self._schedule(ctx)
        schedule[self.TEAM_DAY_INDEX_KEY] = team_days_index
        await self._save_schedule(ctx, schedule)

    async def _match_day(self, ctx):
        return await self.config.guild(ctx.guild).MatchDay()

    async def _save_match_day(self, ctx, match_day):
        await self.config.guild(ctx.guild).MatchDay.set(match_day)

    async def _team_day_match_index(self, ctx, team, match_day):
        team_days_index = await self._team_days_index(ctx)
        team_days_index =  {k.lower(): (v.lower() if isinstance(v, str) else v) for k, v in team_days_index.items()}
        if isinstance(match_day, str):
            match_day = match_day.lower()
        return team_days_index.get(
            self._team_day_key(team.lower(), match_day))

    def _team_day_key(self, team, match_day):
        return "{0}|{1}".format(team, match_day)

    async def _format_match_embed(self, ctx, match_index, user_team_name):
        matches = await self._matches(ctx)
        match = matches[match_index]
        # Match format:
        # match_data = {
        #     'matchDay': match_day,
        #     'matchDate': match_date,
        #     'home': home,
        #     'away': away,
        #     'roomName': roomName,
        #     'roomPass': roomPass,
        #     'stream_details' : <stream details/None>
        # }
        home = match['home']
        away = match['away']

        tier_role = (await self.team_manager._roles_for_team(ctx, home))[1]

        title = "__Match Day {0}: {1}__\n".format(match['matchDay'], match['matchDate'])
        description = "**{0}**\n    versus\n**{1}**\n\n".format(home, away)

        embed = discord.Embed(title=title, description=description, color=tier_role.color)

        player_ratings = self.bot.get_cog("PlayerRatings")
        if player_ratings and await player_ratings.guild_has_players(ctx):
            return await self._create_solo_match_embed(ctx, embed, match, player_ratings, user_team_name, home, away)
            
        return await self._create_normal_match_embed(ctx, embed, match, user_team_name, home, away)

        

    async def _format_match_message(self, ctx, match_index, user_team_name):
        matches = await self._matches(ctx)
        match = matches[match_index]
        # Match format:
        # match_data = {
        #     'matchDay': match_day,
        #     'matchDate': match_date,
        #     'home': home,
        #     'away': away,
        #     'roomName': roomName,
        #     'roomPass': roomPass
        #     'stream_details`: {
        #         'live_stream': live_stream,
        #         'slot': slot,
        #         'time': time
        #      }
        # }
        home = match['home']
        away = match['away']

        message = "__Match Day {0}: {1}__\n".format(match['matchDay'], match['matchDate'])
        message += "**{0}**\n    versus\n**{1}**\n\n".format(home, away)


        player_ratings = self.bot.get_cog("PlayerRatings")
        if player_ratings and await player_ratings.guild_has_players(ctx):
            message += await self._create_solo_match_message(ctx, match, player_ratings, user_team_name, home, away)
            return message
            
        message += await self._create_normal_match_message(ctx, match, user_team_name, home, away)
        return message

    async def get_match_from_day_team(self, ctx, match_day, team_name):
        matches = await self._matches(ctx)
        # Match format:
        # match_data = {
        #     'matchDay': match_day,
        #     'matchDate': match_date,
        #     'home': home,
        #     'away': away,
        #     'roomName': roomName,
        #     'roomPass': roomPass
        # }
        for match in matches:
            if match['matchDay'] == match_day:
                if match['home'].casefold() == team_name.casefold() or match['away'].casefold() == team_name.casefold():
                    return match
        return None

    async def set_match_on_stream(self, ctx, match_day, team_name, stream_info):
        matches = await self._matches(ctx)
        for match in matches:
            if not match['matchDay'] == match_day:
                break 
            if match['home'] == team_name or match['away'] == team_name:
                match['streamDetails'] = stream_info
                await self._save_matches(ctx, matches)
                return True
        return False

    async def remove_match_from_stream(self, ctx, match_day, team_name):
        matches = await self._matches(ctx)
        for match in matches:
            if not match['matchDay'] == match_day:
                break 
            if match['home'] == team_name or match['away'] == team_name:
                match.pop('streamDetails', None)
                await self._save_matches(ctx, matches)
                return True
        return False

    def _create_additional_info(self, user_team_name, home, away, stream_details=None, is_playoffs=False):
        additional_info = ""
        if user_team_name:
            if stream_details:
                if user_team_name.casefold() == home.casefold():
                    additional_info += stream_info.format(
                        home_or_away='home', 
                        time_slot=stream_details['slot'],
                        time=stream_details['time'],
                        live_stream=stream_details['live_stream']
                    )
                elif user_team_name.casefold() == away.casefold():
                    additional_info += stream_info.format(
                        home_or_away='away', 
                        time_slot=stream_details['slot'],
                        time=stream_details['time'],
                        live_stream=stream_details['live_stream']
                    )
            else:
                if user_team_name == home:
                    additional_info += home_info
                elif user_team_name == away:
                    additional_info += away_info
                

        # TODO: Add other info (complaint form, disallowed maps,
        #       enable crossplay, etc.)
        # REGULAR SEASON INFO
        additional_info += regular_info
        # PLAYOFF INFO
        #additional_info += playoff_info
        return additional_info

    async def _create_normal_match_embed(self, ctx, embed, match, user_team_name, home, away):
        embed.add_field(name="Lobby Info", value="Name: **{0}**\nPassword: **{1}**"
                                        .format(match['roomName'], match['roomPass']), inline=False)
        embed.add_field(name="**Home Team:**",
                value=await self.team_manager.format_roster_info(ctx, home), inline=False)
        embed.add_field(name="**Away Team:**",
                value=await self.team_manager.format_roster_info(ctx, away), inline=False)

        try:
            additional_info = self._create_additional_info(user_team_name, home, away, stream_details=match['streamDetails'])
        except KeyError:
            additional_info = self._create_additional_info(user_team_name, home, away)

        embed.add_field(name="Additional Info:", value=additional_info)
        return embed

    async def _create_normal_match_message(self, ctx, match, user_team_name, home, away):
        message = "**Lobby Info:**\nName: **{0}**\nPassword: **{1}**\n\n".format(match['roomName'], match['roomPass'])
        message += "**Home Team:**\n{0}\n".format(await self.team_manager.format_roster_info(ctx, home))
        message += "**Away Team:**\n{0}\n".format(await self.team_manager.format_roster_info(ctx, away))

        try:
            message += self._create_additional_info(user_team_name, home, away, stream_details=match['streamDetails'])
        except KeyError:
            message += self._create_additional_info(user_team_name, home, away)

        return message

    async def _create_solo_match_embed(self, ctx, embed, match, player_ratings_cog, user_team_name, home, away):
        embed.add_field(name="**Home Team:**",
                value=await self.team_manager.format_roster_info(ctx, home), inline=False)
        embed.add_field(name="**Away Team:**",
                value=await self.team_manager.format_roster_info(ctx, away), inline=False)
        message = ""
        seed = await player_ratings_cog.get_player_seed(ctx, user_team_name)
        if seed:
            message += await self._create_solo_user_matchups_message(ctx, match, player_ratings_cog, user_team_name, home, away, seed)
        else:
            message += await self._create_generic_solo_matchups_message(ctx, player_ratings_cog, home, away)
        embed.add_field(name="Match Info:", value=message)
        return embed

    async def _create_solo_match_message(self, ctx, match, player_ratings_cog, user_team_name, home, away):
        message = "**Home Team:**\n{0}\n".format(await self.team_manager.format_roster_info(ctx, home))
        message += "**Away Team:**\n{0}\n".format(await self.team_manager.format_roster_info(ctx, away))
        seed = await player_ratings_cog.get_player_seed(ctx, user_team_name)
        if seed:
            message += await self._create_solo_user_matchups_message(ctx, match, player_ratings_cog, user_team_name, home, away, seed)
        else:
            message += await self._create_generic_solo_matchups_message(ctx, player_ratings_cog, home, away)
        return message

    async def _create_solo_user_matchups_message(self, ctx, match, player_ratings_cog, user_team_name, home, away, seed):
        message = ""
        if user_team_name.casefold() == home.casefold():
            ordered_opponent_names, ordered_opponent_seeds = await player_ratings_cog.get_ordered_opponent_names_and_seeds(ctx, seed, True, away)
            message += solo_home_info.format(seed)
            message += "\n\n**Lobby Info:**\nName: **{0}**\nPassword: **{1}**\n\n".format(match['roomName'] + str(seed), match['roomPass'] + str(seed))
            message += solo_home_match_info.format(first_match_descr, ordered_opponent_names[0], first_match_time)
            message += solo_home_match_info.format(second_match_descr, ordered_opponent_names[1], second_match_time)
            message += solo_home_match_info.format(third_match_descr, ordered_opponent_names[2], third_match_time)
        else:
            ordered_opponent_names, ordered_opponent_seeds = await player_ratings_cog.get_ordered_opponent_names_and_seeds(ctx, seed, False, home)
            message += solo_away_info.format(seed)
            message += "\n\n{0}".format(solo_away_match_info.format(first_match_descr, ordered_opponent_names[0], first_match_time, 
                match['roomName'] + str(ordered_opponent_seeds[0]), match['roomPass'] + str(ordered_opponent_seeds[0])))
            message += "\n\n{0}".format(solo_away_match_info.format(second_match_descr, ordered_opponent_names[1], second_match_time, 
                match['roomName'] + str(ordered_opponent_seeds[1]), match['roomPass'] + str(ordered_opponent_seeds[1])))
            message += "\n\n{0}".format(solo_away_match_info.format(third_match_descr, ordered_opponent_names[2], third_match_time, 
                match['roomName'] + str(ordered_opponent_seeds[2]), match['roomPass'] + str(ordered_opponent_seeds[2])))
        return message

    async def _create_generic_solo_matchups_message(self, ctx, player_ratings_cog, home, away):
        message = ""
        try:
            # First match
            message += "\n\nThe first **one game** series will begin at {0} and will include the following matchups: ".format(first_match_time)
            message += "```"
            message += await self._create_matchup_string(ctx, player_ratings_cog, home, away, 1, 3)
            message += "\n" + await self._create_matchup_string(ctx, player_ratings_cog, home, away, 2, 1)
            message += "\n" + await self._create_matchup_string(ctx, player_ratings_cog, home, away, 3, 2)
            message += "```"
            # Second match
            message += "\n\nThe second **one game** series will begin at {0} and will include the following matchups: ".format(second_match_time)
            message += "```"
            message += await self._create_matchup_string(ctx, player_ratings_cog, home, away, 1, 2)
            message += "\n" + await self._create_matchup_string(ctx, player_ratings_cog, home, away, 2, 3)
            message += "\n" + await self._create_matchup_string(ctx, player_ratings_cog, home, away, 3, 1)
            message += "```"
            # Third match
            message += "\n\nThe final **three game** series will begin at {0} and will include the following matchups: ".format(third_match_time)
            message += "```"
            message += await self._create_matchup_string(ctx, player_ratings_cog, home, away, 1, 1)
            message += "\n" + await self._create_matchup_string(ctx, player_ratings_cog, home, away, 2, 2)
            message += "\n" + await self._create_matchup_string(ctx, player_ratings_cog, home, away, 3, 3)
            message += "```"
        except:
            message = "There was an error getting the matchups for this match."
        return message

    async def _create_matchup_string(self, ctx, player_ratings_cog, home, away, home_seed, away_seed):
        away_player_nick = str((await player_ratings_cog.get_member_by_team_and_seed(ctx, away, away_seed)).nick) # We convert to string to handle None cases
        home_player_nick = str((await player_ratings_cog.get_member_by_team_and_seed(ctx, home, home_seed)).nick) # We convert to string to handle None cases
        return solo_matchup.format(away_player = away_player_nick, home_player = home_player_nick)

    def _generate_name_pass(self):
        return room_pass[random.randrange(len(room_pass))]

# TODO: Load from file?
room_pass = [
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
    'hypnotik', 'illuminata', 'infinium', 'kalos', 'lobo', 'looper',
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

home_info = ("You are the **home** team. You will create the "
            "room using the above information. Contact the "
            "other team when your team is ready to begin the "
            "match. Do not join a team until the away team starts "
            "to.\nRemember to ask before the match begins if the other "
            "team would like to switch server region after 2 "
            "games.")

away_info = ("You are the **away** team. You will join the room "
            "using the above information once the other team "
            "contacts you. Do not begin joining a team until "
            "your entire team is ready to begin playing.")

solo_home_info = ("You are on the **home** team. You are the {0} seed. "
            "You are responsible for hosting the lobby for all of "
            "your matches with the following lobby information: ")

solo_away_info = ("You are on the **away** team. You are the {0} seed. "
            "You will participate in the following matchups: ")
            

solo_home_match_info = ("Your {0} will be against `{1}` at {2}.\n\n")

solo_away_match_info = ("Your {0} will be against `{1}` at "
            "{2} with the following lobby info: "
            "\nName: **{3}**"
            "\nPassword: **{4}**")

first_match_descr = ("first **one game** match")

second_match_descr = ("second **one game** match")

third_match_descr = ("**three game** series")

first_match_time = ("10:00 pm ET (7:00 pm PT)")

second_match_time = ("approximately 10:10 pm ET (7:10 pm PT)")

third_match_time = ("approximately 10:20 pm ET (7:20 pm PT)")

solo_matchup = ("{away_player:25s} vs.\t{home_player}")

stream_info = ("**This match is scheduled to play on stream ** "
            "(Time slot {time_slot}: {time})"
            "\nYou are the **{home_or_away}** team. "
            "A member of the Media Committee will inform you when the lobby is ready. "
            "Do not join the lobby unless you are playing in the upcoming game. "
            "Players should not join until instructed to do so via in-game chat. "
            "\nRemember to inform the Media Committee what server "
            "region your team would like to play on before games begin."
            "\n\nLive Stream: <{live_stream}>")
            
regular_info = ("\n\nBe sure that **crossplay is enabled**. Be sure to save replays "
                "and screenshots of the end-of-game scoreboard. Do not leave "
                "the game until screenshots have been taken. "
                "These must be uploaded by one member of your team after the 4-game series "
                "is over. Remember that the deadline to reschedule matches is "
                "at 10 minutes before the currently scheduled match time. They "
                "can be scheduled no later than 11:59 PM ET on the original match day.\n\n")

playoff_info = ("Playoff matches are a best of 5 series for every round until the finals. "
                "Screenshots and replays do not need to be uploaded to the website for "
                "playoff matches but you will need to report the scores in #score-reporting.\n\n")
