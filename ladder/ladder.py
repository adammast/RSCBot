import discord
import collections
import operator
import random
import asyncio
import datetime
import uuid

from queue import Queue
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions

team_size = 3
minimum_game_time = 600 #Seconds (10 Minutes)
verify_timeout = 15
k_factor = 50

defaults = {"CategoryChannel": None, "HelperRole": None, "Games": {}, "GamesPlayed": 0, "Teams": {}, "Scores": []}

class Ladder(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567880, force_registration=True)
        self.config.register_guild(**defaults)
        self.games = []
        self.teams = []

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def addTeam(self, ctx, name, captain: discord.Member, *players: discord.Member):
        await self.load_teams(ctx, False)
        for team in self.teams:
            if team.name == name:
                await ctx.send(":x: {} is already the name of a team.".format(name))
                return

        player_list = list(players)
        if captain not in player_list:
            player_list.append(captain)
        if len(player_list) != team_size:
            await ctx.send(":x: Teams need to have {} players".format(team_size))
            return
        
        team = Team(name, captain, player_list, 0, 0, 1500)
        self.teams.append(team)
        await self._save_teams(ctx, self.teams)

    @commands.guild_only()
    @commands.command()
    async def getTeamInfo(self, ctx, team_name):
        await self.load_teams(ctx, False)
        for team in self.teams:
            if team.name == team_name:
                await ctx.send(embed=self.embed_team_info(ctx, team))
                return

        await ctx.send(":x: There's no team with the name: {}".format(team_name))

    def update_elo(self, team_1_elo, team_2_elo, result):
        """Calculates and returns the new Elo ratings for the two teams based on their match results and the K-factor.
        Result param should be a decimal between 0 and 1 relating to the match results for team 1, i.e. a result of 1 
        means team 1 won all the games in the match, a result of .25 means team 1 won 25% of the games in the match."""
        elo_dif = team_1_elo - team_2_elo
        exponent = -1 * (elo_dif / 100)
        expectation = 1 / (1 + pow(10, exponent))
        team_1_new_elo = round(team_1_elo + (k_factor * (result - expectation)))
        team_2_new_elo = round(team_2_elo + (k_factor * ((1 - result) - (1 - expectation))))
        return team_1_new_elo, team_2_new_elo

    def embed_team_info(self, ctx, team: Team):
        embed = discord.Embed(title="{0} Team Info".format(team.name), color=discord.Colour.blue())
        embed.add_field(name="Captain", value="{}\n".format(team.captain.mention), inline=False)
        embed.add_field(name="Players", value="{}\n".format(", ".join([player.mention for player in team.players])), inline=False)
        embed.add_field(name="Games Played", value="{}\n".format(team.wins + team.losses), inline=False)
        embed.add_field(name="Record", value="{0} - {1}\n".format(team.wins, team.losses), inline=False)
        embed.add_field(name="Elo Rating", value="{}\n".format(team.elo_rating), inline=False)
        return embed

    async def load_teams(self, ctx, force_load):
        if self.teams is None or self.teams == [] or force_load:
            teams = await self._teams(ctx)
            team_list = []
            for key, value in teams.items():
                name = value["Name"]
                captain = ctx.guild.get_member(value["Captain"])
                players = [ctx.guild.get_member(x) for x in value["Players"]]
                wins = value["Wins"]
                losses = value["Losses"]
                elo_rating = value["EloRating"]
                team = Team(name, captain, players, wins, losses, elo_rating)
                team.id = int(key)
                team_list.append(team)

            self.teams = team_list

    async def _teams(self, ctx):
        return await self.config.guild(ctx.guild).Teams()

    async  def _save_teams(self, ctx, teams):
        team_dict = {}
        for team in teams:
            team_dict[team.id] = team._to_dict()
        await self.config.guild(ctx.guild).Teams.set(team_dict)

    async def load_games(self, ctx, force_load):
        if self.games is None or self.games == [] or force_load:
            self.load_teams(ctx, force_load)
            games = await self._games(ctx)
            game_list = []
            for key, value in games.items():
                text_channel = ctx.guild.get_channel(value["TextChannel"])
                voice_channels = [ctx.guild.get_channel(x) for x in value["VoiceChannels"]]
                blue_team_id = value["Blue"]
                orange_team_id = value["Orange"]
                blue_team = next(x for x in self.teams if x.id == blue_team_id)
                orange_team = next(x for x in self.teams if x.id == orange_team_id)
                game = Game(blue_team, orange_team, text_channel, voice_channels)
                game.id = int(key)
                game.roomName = value["RoomName"]
                game.roomPass = value["RoomPass"]
                game.scoreReported = value["ScoreReported"]
                game_list.append(game)

            self.games = game_list

    async def _games(self, ctx):
        return await self.config.guild(ctx.guild).Games()

    async  def _save_games(self, ctx, games):
        game_dict = {}
        for game in games:
            game_dict[game.id] = game._to_dict()
        await self.config.guild(ctx.guild).Games.set(game_dict)

    async def _scores(self, ctx):
        return await self.config.guild(ctx.guild).Scores()

    async def _save_scores(self, ctx, scores):
        await self.config.guild(ctx.guild).Scores.set(scores)

    async def _games_played(self, ctx):
        return await self.config.guild(ctx.guild).GamesPlayed()

    async def _save_games_played(self, ctx, games_played):
        await self.config.guild(ctx.guild).GamesPlayed.set(games_played)

    async def _category(self, ctx):
        return ctx.guild.get_channel(await self.config.guild(ctx.guild).CategoryChannel())

    async def _save_category(self, ctx, category):
        await self.config.guild(ctx.guild).CategoryChannel.set(category)

    async def _helper_role(self, ctx):
        return ctx.guild.get_role(await self.config.guild(ctx.guild).HelperRole())

    async def _save_helper_role(self, ctx, helper_role):
        await self.config.guild(ctx.guild).HelperRole.set(helper_role)

class Team:
    def __init__(self, name, captain, players, wins, losses, elo_rating):
        self.id = uuid.uuid4().int
        self.name = name
        self.captain = captain
        self.players = set(players)
        self.games_played = wins + losses
        self.wins = wins
        self.losses = losses
        self.elo_rating = elo_rating

    def _to_dict(self):
        return {
            "Name": self.name,
            "Captain": self.captain,
            "Players": [x.id for x in self.players],
            "Wins": self.wins,
            "Losses": self.losses,
            "EloRating": self.elo_rating
        }

class Game:
    def __init__(self, blue_team: Team, orange_team: Team, text_channel, voice_channels):
        self.id = uuid.uuid4().int
        self.captains = [blue_team.captain, orange_team.captain]
        self.players = blue_team.players.union(orange_team.players)
        self.blue = blue_team
        self.orange = orange_team
        self.roomName = self._generate_name_pass()
        self.roomPass = self._generate_name_pass()
        self.textChannel = text_channel
        self.voiceChannels = voice_channels #List of voice channels: [Blue, Orange]
        self.scoreReported = False

    def _to_dict(self):
        return {
            "Blue": self.blue.id,
            "Orange": self.orange.id,
            "RoomName": self.roomName,
            "RoomPass": self.roomPass,
            "TextChannel": self.textChannel.id,
            "VoiceChannels": [x.id for x in self.voiceChannels],
            "ScoreReported": self.scoreReported
        }

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