import collections
import datetime
import uuid
import struct
from queue import Queue
from typing import List
from .strings import Strings

import discord

SELECTION_MODES = {
    0x1F3B2: Strings.RANDOM_TS,         # game_die
    0x1F1E8: Strings.CAPTAINS_TS,       # C
    0x0262F: Strings.BALANCED_TS,       # yin_yang
    0x1F530: Strings.SELF_PICKING_TS,   # beginner
    0x1F5F3: Strings.VOTE_TS            # ballot_box
}

class SixMansQueue:
    def __init__(self, name, guild: discord.Guild, channels: List[discord.TextChannel],
        points, players, gamesPlayed, maxSize, teamSelection=Strings.RANDOM_TS, category: discord.CategoryChannel=None, lobby_vc: discord.VoiceChannel=None):
        self.id = uuid.uuid4().int
        self.name = name
        self.queue = PlayerQueue()
        self.guild = guild
        self.channels = channels
        self.points = points
        self.players = players
        self.gamesPlayed = gamesPlayed
        self.maxSize = maxSize
        self.teamSelection = teamSelection
        self.category = category
        self.lobby_vc = lobby_vc
        self.activeJoinLog = {}
        # TODO: active join log could maintain queue during downtime

    def _put(self, player):
        self.queue.put(player)
        # self.activeJoinLog[player.id] = datetime.datetime.now()

    def _get(self):
        player = self.queue.get()
        try:
            del self.activeJoinLog[player.id]
        except:
            pass
        return player

    def get_player_summary(self, player: discord.User):
        try:
            return self.players[str(player.id)]
        except:
            return None

    def _remove(self, player):
        self.queue._remove(player)
        try:
            del self.activeJoinLog[player.id]
        except:
            pass

    def _queue_full(self):
        return self.queue.qsize() >= self.maxSize

    async def send_message(self, message='', embed=None):
        messages = []
        for channel in self.channels:
            messages.append(await channel.send(message, embed=embed))
        return messages

    async def set_team_selection(self, team_selection):
        self.teamSelection = team_selection
        emoji = self.get_ts_emoji()
        if emoji:
            await self.send_message("Queue Team Selection has been set to {} **{}**.".format(emoji, team_selection))
        else:
            await self.send_message("Queue Team Selection has been set to **{}**.".format(team_selection))

    def get_ts_emoji(self):
        for key, value in SELECTION_MODES.items():
            if value == self.teamSelection:
                return self._get_pick_reaction(key)
    
    def _get_pick_reaction(self, int_or_hex):
        try:
            if type(int_or_hex) == int:
                return struct.pack('<I', int_or_hex).decode('utf-32le')
            if type(int_or_hex) == str:
                return struct.pack('<I', int(int_or_hex, base=16)).decode('utf-32le') # i == react_hex
        except:
            return None

    def _to_dict(self):
        q_data = {
            "Name": self.name,
            "Channels": [x.id for x in self.channels],
            "Points": self.points,
            "Players": self.players,
            "GamesPlayed": self.gamesPlayed,
            "TeamSelection": self.teamSelection,
            "MaxSize": self.maxSize
        }
        if self.category:
            q_data['Category'] = self.category.id
        if self.lobby_vc:
            q_data['LobbyVC'] = self.lobby_vc.id
        
        return q_data

class PlayerQueue(Queue):
    def _init(self, maxsize):
        self.queue = OrderedSet()

    def _put(self, item):
        self.queue.add(item)

    def _get(self):
        return self.queue.pop()

    def _remove(self, value):
        self.queue.remove(value)

    def __contains__(self, item):
        with self.mutex:
            return item in self.queue


class OrderedSet(collections.MutableSet):
    def __init__(self, iterable=None):
        self.end = end = []
        end += [None, end, end]  # sentinel node for doubly linked list
        self.map = {}  # key --> [key, prev, next]
        if iterable is not None:
            self |= iterable

    def __len__(self):
        return len(self.map)

    def __contains__(self, key):
        return key in self.map

    def add(self, key):
        if key not in self.map:
            end = self.end
            curr = end[1]
            curr[2] = end[1] = self.map[key] = [key, curr, end]

    def discard(self, key):
        if key in self.map:
            key, prev, next = self.map.pop(key)
            prev[2] = next
            next[1] = prev

    def __iter__(self):
        end = self.end
        curr = end[2]
        while curr is not end:
            yield curr[0]
            curr = curr[2]

    def __reversed__(self):
        end = self.end
        curr = end[1]
        while curr is not end:
            yield curr[0]
            curr = curr[1]

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, list(self))

    def __eq__(self, other):
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return set(self) == set(other)
