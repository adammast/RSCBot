import discord
import collections
import operator
import random
import time

from queue import Queue
from discord.ext import commands
from cogs.utils import checks

TEAM_SIZE = 6
CAT_ID = 599665527433986085

class SixMans:

    def __init__(self, bot):
        self.bot = bot
        self.queue = PlayerQueue()
        self.game = None

    CHANNEL_INDEX = 1

    @commands.command(pass_context=True, no_pm=True, aliases=["tc"])
    @checks.admin_or_permissions(manage_server=True)
    async def test_channel(self, ctx):
        await self.create_channel(ctx)


    @commands.command(pass_context=True, no_pm=True, aliases=["qa"])
    @checks.admin_or_permissions(manage_server=True)
    async def queue_all(self, ctx, *members: discord.Member):
        """Mass queueing for testing purposes"""
        for member in members:
            if member in self.queue:
                await self.bot.say("{} is already in queue.".format(member.display_name))
                break
            self.queue.put(member)
            await self.bot.say("{} added to queue. ({:d}/{:d})".format(member.display_name, self.queue.qsize(), TEAM_SIZE))
        if self.queue_full():
            await self.bot.say("Queue is full! Teams are as follows:")
            await self.randomize_teams(ctx)

    @commands.command(pass_context=True, no_pm=True, aliases=["dqa"])
    @checks.admin_or_permissions(manage_server=True)
    async def dequeue_all(self, ctx, *members: discord.Member):
        """Mass queueing for testing purposes"""
        for member in members:
            self.queue.put(member)
            await self.bot.say("{} added to queue. ({:d}/{:d})".format(member.display_name, self.queue.qsize(), TEAM_SIZE))

    @commands.command(pass_context=True, no_pm=True, aliases=["queue"])
    async def q(self, ctx):
        """Add yourself to the queue"""
        player = ctx.message.author

        if player in self.queue:
            await self.bot.say("{} is already in queue.".format(player.display_name))
            return
        if self.busy and player in self.game:
            await self.bot.say("{} is already in a game.".format(player.display_name))
            return

        self.queue.put(player)

        await self.bot.say("{} added to queue. ({:d}/{:d})".format(player.display_name, self.queue.qsize(), TEAM_SIZE))
        if self.queue_full():
            await self.bot.say("Queue is full! Teams are being created.")
            await self.randomize_teams(ctx)

    @commands.command(pass_context=True, no_pm=True, aliases=["dq"])
    async def dequeue(self, ctx):
        """Remove yourself from the queue"""
        player = ctx.message.author

        if player in self.queue:
            self.queue.remove(player)
            await self.bot.say(
                "{} removed from queue. ({:d}/{:d})".format(player.display_name, self.queue.qsize(), TEAM_SIZE))
        else:
            await self.bot.say("{} is not in queue.".format(player.display_name))

    @commands.command(no_pm=True, aliases=["kq"])
    @checks.admin_or_permissions(manage_server=True)
    async def kick_queue(self, player: discord.Member):
        """Remove someone else from the queue"""
        if player in self.queue:
            self.queue.remove(player)
            await self.bot.say(
                "{} removed from queue. ({:d}/{:d})".format(player.display_name, self.queue.qsize(), TEAM_SIZE))
        else:
            await self.bot.say("{} is not in queue.".format(player.display_name))

    def queue_full(self):
        return self.queue.qsize() >= TEAM_SIZE

    async def randomize_teams(self, ctx):
        self.busy = True
        self.create_game()
        channel = await self.create_channel(ctx)

        orange = random.sample(self.game.players, 3)
        for player in orange:
            self.game.add_to_orange(player)

        blue = list(self.game.players)
        for player in blue:
            self.game.add_to_blue(player)

        await self.display_game_info(channel)

        self.busy = False

    async def display_game_info(self, channel):
        embed = discord.Embed(title="6 Mans Game Info", colour=discord.Colour.blue())
        embed.add_field(name="Orange Team", value="{}".format(", ".join([player.mention for player in self.game.orange])))
        embed.add_field(name="Blue Team", value="{}".format(", ".join([player.mention for player in self.game.blue])))
        embed.add_field(name="Lobby Info", value="Name = {0}\nPass = {1}".format(self.game.roomName, self.game.roomPass))
        await self.bot.send_message(channel, embed=embed)

    def create_game(self):
        players = [self.queue.get() for _ in range(TEAM_SIZE)]
        self.game = Game(players)

    async def create_channel(self, ctx):
        server = ctx.message.server
        channel = await self.bot.create_channel(server, '6mans-channel-{}'.format(self.CHANNEL_INDEX), type=discord.ChannelType.text)
        self.CHANNEL_INDEX += 1
        return channel

class Game:
    def __init__(self, players):
        self.players = set(players)
        self.captains = random.sample(self.players, 2)
        self.orange = set()
        self.blue = set()
        self.roomName = self._generate_name_pass()
        self.roomPass = self._generate_name_pass()

    def add_to_blue(self, player):
        self.players.remove(player)
        self.blue.add(player)

    def add_to_orange(self, player):
        self.players.remove(player)
        self.orange.add(player)

    def __contains__(self, item):
        return item in self.players or item in self.orange or item in self.blue

    def _generate_name_pass(self):
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
        return set[random.randrange(len(set))]

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

    def pop(self, last=True):
        if not self:
            raise KeyError('set is empty')
        key = self.end[1][0] if last else self.end[2][0]
        self.discard(key)
        return key

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, list(self))

    def __eq__(self, other):
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return set(self) == set(other)


class PlayerQueue(Queue):
    def _init(self, maxsize):
        self.queue = OrderedSet()

    def _put(self, item):
        self.queue.add(item)

    def _get(self):
        return self.queue.pop()

    def remove(self, value):
        self.queue.remove(value)

    def __contains__(self, item):
        with self.mutex:
            return item in self.queue

def setup(bot):
    bot.add_cog(SixMans(bot))