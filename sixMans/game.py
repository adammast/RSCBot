import discord
import random
import uuid
import struct

# from redbot.core import Config
# from redbot.core import commands
# from redbot.core import checks
# from redbot.core.utils.predicates import ReactionPredicate
# from redbot.core.utils.menus import start_adding_reactions


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
        # Pick captains
        self.captains = random.sample(self.players, 2)
        self.blue.add(self.captains[0])
        self.orange.add(self.captains[1])

        pick_order = ['blue', 'orange', 'orange']

        pickable = list(self.players)
        pickable.remove(self.captains[0])
        pickable.remove(self.captains[1])

        # Assign reactions to remaining players
        self.react_player_picks = {}
        react_hex = 0x1F1E6
        for i in range(len(pickable)):
            react_hex_i = hex(react_hex+i)
            self.react_player_picks[react_hex_i] = pickable[i]
        
        # Get player pick embed
        embed = self._get_captains_embed('blue')
        self.teams_message = await self.textChannel.send(embed=embed)
        
        for react_hex in self.react_player_picks.keys():
            react = struct.pack('<I', int(react_hex, base=16)).decode('utf-32le')
            await self.teams_message.add_reaction(react)

    # here
    async def process_captains_pick(self, reaction, user):
        teams_complete = False
        pick_i = len(self.blue)+len(self.orange)-2
        pick_order = ['blue', 'orange', 'orange', 'blue']
        pick = pick_order[pick_i]
        captain_picking = self.captains[0] if pick == 'blue' else self.captains[1]
        
        if user != captain_picking and user.id != 302079469882179585:
            return False
        
        # get player from reaction
        player_picked = self._get_player_from_reaction_emoji(ord(reaction.emoji))
        await self.teams_message.clear_reaction(reaction.emoji)
        
        # add to correct team, update teams embed
        self.blue.add(player_picked) if pick == 'blue' else self.orange.add(player_picked)
        
        # TODO: automatically process last pick
        picks_remaining = list(self.react_player_picks.keys())
        if len(picks_remaining) > 1:
            embed = self._get_captains_embed(pick_order[pick_i+1])
            await self.teams_message.edit(embed=embed)
        
        elif len(picks_remaining) == 1:
            last_pick = 'blue' if len(self.orange) > len(self.blue) else 'orange'
            last_pick_key = picks_remaining[0]
            last_player = self.react_player_picks[last_pick_key]
            del self.react_player_picks[last_pick_key]
            await self.teams_message.clear_reactions()
            self.blue.add(last_player) if last_pick == 'blue' else self.orange.add(last_player)
            teams_complete = True
            embed = self._get_captains_embed(None, guild=last_player.guild)
            await self.teams_message.edit(embed=embed)
        return teams_complete

    def _get_captains_embed(self, pick, guild=None):
        # Determine who picks next
        if pick:
            team_color = discord.Colour.blue() if pick == 'blue' else discord.Colour.orange()
            player = self.captains[0] if pick == 'blue' else self.captains[1]
            description = "**{}**, pick a player to join the **{}** team.".format(player.name, pick)

        else:
            team_color = discord.Colour.green()
            description="Teams have been set!"

        embed = discord.Embed(
            title="{} Game | Team Selection".format(self.textChannel.name),
            color=team_color,
            description=description
        )

        if pick:
            embed.set_thumbnail(url=player.avatar_url)
        elif guild:
            embed.set_thumbnail(url=guild.icon_url)

        # List teams as they stand
        embed.add_field(name="Blue Team", value=', '.join(p.mention for p in self.blue), inline=False)
        embed.add_field(name="Orange Team", value=', '.join(p.mention for p in self.orange), inline=False)

        # List available players
        pickable_players = self._get_pickable_players_str()
        if pickable_players:
            embed.add_field(name="Available Players", value=pickable_players, inline=False)
        return embed

    def _get_player_from_reaction_emoji(self, emoji):
        target_key = None
        target_value = None
        for e, player in self.react_player_picks.items():
            if emoji == int(e, base=16): # or ord(emoji) == ord(e) or str(emoji) == str(e):
                target_key = e
                target_value = player
                break
        if target_key:
            del self.react_player_picks[target_key]
        return target_value

    def _get_pick_reaction(self, int_or_hex):
        try:
            if type(int_or_hex) == int:
                return struct.pack('<I', int_or_hex).decode('utf-32le')
            if type(int_or_hex) == str:
                return struct.pack('<I', int(int_or_hex, base=16)).decode('utf-32le') # i == react_hex
        except:
            return None
    
    def _get_pickable_players_str(self):
        players = ""
        for react_hex, player in self.react_player_picks.items():
            react = self._get_pick_reaction(int(react_hex, base=16))
            players += "{} {}\n".format(react, player.mention)
        return players

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
