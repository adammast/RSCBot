import discord
import collections
import operator
import random
import asyncio
import datetime
import uuid
import struct

from queue import Queue
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions


team_size = 6
minimum_game_time = 600     # Seconds (10 Minutes)
player_timeout_time = 14400 # How long players can be in a queue in seconds (4 Hours)
loop_time = 5               # How often to check the queues in seconds
verify_timeout = 15
pp_play_key = "Play"
pp_win_key = "Win"
player_points_key = "Points"
player_gp_key = "GamesPlayed"
player_wins_key = "Wins"
queues_key = "Queues"

defaults = {
    "CategoryChannel": None,
    "HelperRole": None,
    "AutoMove": False,
    "QLobby": None,
    "DefaultTeamSelection": "Random",
    "Games": {},
    "Queues": {},
    "GamesPlayed": 0,
    "Players": {},
    "Scores": []
}

class Game:
    def __init__(self, players, text_channel: discord.TextChannel, voice_channels, queue_id, automove=False):
        self.id = uuid.uuid4().int
        self.players = set(players)
        self.captains = []
        self.blue = set()
        self.orange = set()
        self.roomName = self._generate_name_pass()
        self.roomPass = self._generate_name_pass()
        self.textChannel = text_channel
        self.voiceChannels = voice_channels #List of voice channels: [Blue, Orange]
        self.queueId = queue_id
        self.scoreReported = False
        self.automove = automove
        self.teams_message = None
        # self.voted_remake = []
        # self.remake_embed = None

    
    async def append_channel_short_codes(self):
        await self.append_short_code_tc()
        await self.append_short_code_vc()

    async def append_short_code_tc(self):
        await self.textChannel.edit(name="{}-{}".format(str(self.id)[-3:], self.textChannel.name))

    async def append_short_code_vc(self):
        for vc in self.voiceChannels:
            await vc.edit(name="{} | {}".format(str(self.id)[-3:], vc.name))

    async def add_to_blue(self, player):
        self.players.remove(player)
        self.blue.add(player)

        if self.automove:
            blue_vc, orange_vc = self.voiceChannels
            await blue_vc.set_permissions(player, connect=True)
            await orange_vc.set_permissions(player, connect=False)
            try:
                await player.move_to(blue)
            except:
                pass

    async def add_to_orange(self, player):
        self.players.remove(player)
        self.orange.add(player)

        if self.automove:
            blue_vc, orange_vc = self.voiceChannels
            await blue_vc.set_permissions(player, connect=False)
            await orange_vc.set_permissions(player, connect=True)
            try:
                await player.move_to(orange_vc)
            except:
                pass

    async def pick_random_teams(self):
        self.shuffle_players()

    async def shuffle_players(self):
        self.blue = set()
        self.orange = set()
        for player in random.sample(self.players, int(len(self.players)/2)):
            await self.add_to_orange(player)
        blue = [player for player in self.players]
        for player in blue:
            await self.add_to_blue(player)
        self.reset_players()
        self.get_new_captains_from_teams()

    async def captains_pick_teams(self):
        self.captains = random.sample(self.players, 2)
        self.blue.add(self.captains[0])
        self.orange.add(self.captains[1])

        pick_order = ['blue', 'orange', 'orange']

        # for pick in pick_order:
        pick = 'orange'
        team_color = discord.Colour.blue() if pick == 'blue' else discord.Colour.orange()
        player = self.captains[0]
        embed = discord.Embed(
            title="{} Game | Team Selection".format(self.textChannel.name),
            color=team_color,
            description="**{}**, pick a player to join the **{}** team.".format(player.name, pick)  
        )
        embed.set_thumbnail(url=player.avatar_url)
        embed.add_field(name="Blue Team", value=', '.join(p.mention for p in self.blue), inline=False)
        embed.add_field(name="Orange Team", value=', '.join(p.mention for p in self.orange), inline=False)

        pickable = list(self.players)
        pickable.remove(self.captains[0])
        pickable.remove(self.captains[1])
        
        self.react_player_picks = {}
        react_hex = 0x1F1E6
        for i in range(len(pickable)):
            react_hex_i = hex(react_hex+i)
            react_i = struct.pack('<I', react_hex+i).decode('utf-32le')
            self.react_player_picks[react_i] = pickable[i]

        reactions, pickable_players = self._get_pickable_players_str()
        embed.add_field(name="Available Players", value=pickable_players, inline=False)
        self.teams_message = await self.textChannel.send(embed=embed)
        for reaction in reactions:
            await self.teams_message.add_reaction(reaction)

    async def process_captains_pick(self, reaction, user):
        pass

    def _get_pickable_players_str(self):
        reactions = []
        players = ""
        for react, player in self.react_player_picks.items():
            reactions.append(react)
            players += "{} {}\n".format(react, player.mention)
        return reactions, players

    async def pick_balanced_teams(self):
        pass

    def reset_players(self):
        self.players.update(self.orange)
        self.players.update(self.blue)

    def get_new_captains_from_teams(self):
        self.captains = []
        self.captains.append(random.sample(list(self.blue), 1)[0])
        self.captains.append(random.sample(list(self.orange), 1)[0])

    def __contains__(self, item):
        return item in self.players or item in self.orange or item in self.blue

    def _to_dict(self):
        return {
            "Players": [x.id for x in self.players],
            "Captains": [x.id for x in self.captains],
            "Blue": [x.id for x in self.blue],
            "Orange": [x.id for x in self.orange],
            "RoomName": self.roomName,
            "RoomPass": self.roomPass,
            "TextChannel": self.textChannel.id,
            "VoiceChannels": [x.id for x in self.voiceChannels],
            "QueueId": self.queueId,
            "ScoreReported": self.scoreReported,
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
