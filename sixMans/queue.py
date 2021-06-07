import collections
import datetime
import uuid
from queue import Queue
from typing import List

import discord


class SixMansQueue:
    def __init__(self, name, guild: discord.Guild, channels: List[discord.TextChannel], points, players, gamesPlayed, queueMaxSize):
        self.id = uuid.uuid4().int
        self.name = name
        self.queue = PlayerQueue()
        self.guild = guild
        self.channels = channels
        self.points = points
        self.players = players
        self.gamesPlayed = gamesPlayed
        self.queueMaxSize = queueMaxSize
        self.activeJoinLog = {}

    def _put(self, player):
        self.queue.put(player)
        self.activeJoinLog[player.id] = datetime.datetime.now()

    def _get(self):
        player = self.queue.get()
        try:
            del self.activeJoinLog[player.id]
        except:
            pass
        return player

    def _remove(self, player):
        self.queue._remove(player)
        try:
            del self.activeJoinLog[player.id]
        except:
            pass

    def _queue_full(self):
        return self.queue.qsize() >= self.queueMaxSize

    async def send_message(self, message='', embed=None):
        for channel in self.channels:
            await channel.send(message, embed=embed)

    def _to_dict(self):
        return {
            "Name": self.name,
            "Channels": [x.id for x in self.channels],
            "Points": self.points,
            "Players": self.players,
            "GamesPlayed": self.gamesPlayed
        }


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
