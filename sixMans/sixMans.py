import discord
import collections
import operator
import random
import time

from queue import Queue
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks

team_size = 6
pp_play_key = "Play"
pp_win_key = "Win"
player_points_key = "Points"
player_gp_key = "GamesPlayed"
player_wins_key = "Wins"

defaults = {"CategoryChannel": None, "QueueNames": [], "Queues": {}, "GamesPlayed": 0, "Players": {}, "Scores": []}

class SixMans(commands.Cog):

    def __init__(self):
        self.config = Config.get_conf(self, identifier=1234567896, force_registration=True)
        self.config.register_guild(**defaults)
        self.queues = []
        self.games = []
        self.players = {}
        self.scores = []
        self.busy = False

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def addNewQueue(self, ctx, name, points_per_play: int, points_per_win: int, *channels):
        queue_channels = []
        for channel in channels:
            queue_channels.append(await commands.TextChannelConverter().convert(ctx, channel))
        points = {pp_play_key: points_per_play, pp_win_key: points_per_win}
        six_mans_queue = SixMansQueue(name, queue_channels, points, {}, 0)
        self.queues.append(six_mans_queue)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def getQueueNames(self, ctx):
        queue_names = ""
        for queue in self.queues:
            queue_names += queue.name
        await ctx.send("Queues set up in server:\n```{0}```".format(queue_names))

    @commands.guild_only()
    @commands.command(aliases=["qa"])
    @checks.admin_or_permissions(manage_guild=True)
    async def queue_all(self, ctx, *members: discord.Member):
        """Mass queueing for testing purposes"""
        six_mans_queue = self._get_queue(ctx)
        for member in members:
            if member in six_mans_queue.queue:
                await ctx.send("{} is already in queue.".format(member.display_name))
                break
            six_mans_queue.queue.put(member)
            await ctx.send("{} added to queue. ({:d}/{:d})".format(member.display_name, six_mans_queue.queue.qsize(), team_size))
        if six_mans_queue.queue_full():
            await ctx.send("Queue is full! Teams are being created.")
            await self.randomize_teams(ctx, six_mans_queue)

    @commands.guild_only()
    @commands.command(aliases=["queue"])
    async def q(self, ctx):
        """Add yourself to the queue"""
        six_mans_queue = self._get_queue(ctx)
        player = ctx.message.author

        if player in six_mans_queue.queue:
            await ctx.send("{} is already in queue.".format(player.display_name))
            return
        for game in self.games:
            if player in game:
                await ctx.send("{} is already in a game.".format(player.display_name))
                return

        six_mans_queue.queue.put(player)

        await ctx.send("{} added to queue. ({:d}/{:d})".format(player.display_name, six_mans_queue.queue.qsize(), team_size))
        if six_mans_queue.queue_full():
            await ctx.send("Queue is full! Teams are being created.")
            await self.randomize_teams(ctx, six_mans_queue)

    @commands.guild_only()
    @commands.command(aliases=["dq"])
    async def dequeue(self, ctx):
        """Remove yourself from the queue"""
        six_mans_queue = self._get_queue(ctx)
        player = ctx.message.author

        if player in six_mans_queue.queue:
            six_mans_queue.queue.remove(player)
            await ctx.send(
                "{} removed from queue. ({:d}/{:d})".format(player.display_name, six_mans_queue.queue.qsize(), team_size))
        else:
            await ctx.send("{} is not in queue.".format(player.display_name))

    @commands.guild_only()
    @commands.command(aliases=["kq"])
    @checks.admin_or_permissions(manage_guild=True)
    async def kick_queue(self, ctx, player: discord.Member):
        """Remove someone else from the queue"""
        six_mans_queue = self._get_queue(ctx)
        if player in six_mans_queue.queue:
            six_mans_queue.queue.remove(player)
            await ctx.send(
                "{} removed from queue. ({:d}/{:d})".format(player.display_name, six_mans_queue.queue.qsize(), team_size))
        else:
            await ctx.send("{} is not in queue.".format(player.display_name))

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setCategory(self, ctx, category_channel: discord.CategoryChannel):
        """Sets the six mans category channel where all six mans channels will be created under"""
        await self._save_category(ctx, category_channel.id)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def getCategory(self, ctx):
        """Gets the channel currently assigned as the transaction channel"""
        try:
            await ctx.send("Six mans category channel set to: {0}".format((await self._category(ctx)).mention))
        except:
            await ctx.send(":x: Six mans category channel not set")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def unsetCategory(self, ctx):
        """Unsets the six mans category channel. Six mans channels will not be created if this is not set"""
        await self._save_category(ctx, None)
        await ctx.send("Done")

    async def randomize_teams(self, ctx, six_mans_queue):
        self.busy = True
        game = await self.create_game(ctx, six_mans_queue)

        orange = random.sample(game.players, 3)
        for player in orange:
            game.add_to_orange(player)
        
        blue = list(game.players)
        for player in blue:
            game.add_to_blue(player)

        game.reset_players()
        game.get_new_captains_from_teams()

        await self.display_game_info(game)

        self.games.append(game)

        self.busy = False

    async def display_game_info(self, game):
        await game.channel.send("{}\n".format(", ".join([player.mention for player in game.players])))
        embed = discord.Embed(title="6 Mans Game Info", color=discord.Colour.blue())
        embed.add_field(name="Orange Team", value="{}\n".format(", ".join([player.mention for player in game.orange])), inline=False)
        embed.add_field(name="Blue Team", value="{}\n".format(", ".join([player.mention for player in game.blue])), inline=False)
        embed.add_field(name="Lobby Info", value="**Username:** {0}\n**Password:** {1}".format(game.roomName, game.roomPass), inline=False)
        await game.channel.send(embed=embed)

    async def create_game(self, ctx, six_mans_queue):
        players = [six_mans_queue.queue.get() for _ in range(team_size)]
        channel = await self.create_channel(ctx, six_mans_queue)
        for player in players:
            await channel.set_permissions(player, read_messages=True)
        return Game(players, channel)

    async def create_channel(self, ctx, six_mans_queue):
        guild = ctx.message.guild
        channel = await guild.create_text_channel(six_mans_queue.name, 
            overwrites= {
                guild.default_role: discord.PermissionOverwrite(read_messages=False)
            },
            category= await self._category(ctx))
        return channel

    def _get_queue(self, ctx):
        for six_mans_queue in self.queues:
            for channel in six_mans_queue.channels:
                if channel == ctx.channel:
                    return six_mans_queue

    async def _category(self, ctx):
        return ctx.guild.get_channel(await self.config.guild(ctx.guild).CategoryChannel())

    async def _save_category(self, ctx, category):
        await self.config.guild(ctx.guild).CategoryChannel.set(category)

class Game:
    def __init__(self, players, channel):
        self.players = set(players)
        self.captains = list(random.sample(self.players, 2))
        self.orange = set()
        self.blue = set()
        self.roomName = self._generate_name_pass()
        self.roomPass = self._generate_name_pass()
        self.channel = channel

    def add_to_blue(self, player):
        self.players.remove(player)
        self.blue.add(player)

    def add_to_orange(self, player):
        self.players.remove(player)
        self.orange.add(player)

    def reset_players(self):
        self.players.update(self.orange)
        self.players.update(self.blue)

    def get_new_captains_from_teams(self):
        self.captains.append(list(self.orange)[0])
        self.captains.append(list(self.blue)[0])

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

class SixMansQueue:
    def __init__(self, name, channels, points, players, gamesPlayed):
        self.name = name
        self.queue = PlayerQueue()
        self.channels = channels
        self.points = points
        self.players = players
        self.gamesPlayed = gamesPlayed

    def _givePoints(self, winningPlayers, losingPlayers):
        for player in winningPlayers:
            if player.id in self.players:
                player_dict = self.players[player.id]
                player_dict[player_points_key] += (self.points[pp_play_key] + self.points[pp_win_key])
                player_dict[player_gp_key] += 1
                player_dict[player_wins_key] +=1
            else:
                self.players[player.id] = {
                    player_points_key: self.points[pp_play_key] + self.points[pp_win_key],
                    player_gp_key: 1,
                    player_wins_key: 1
                }

        for player in losingPlayers:
            if player.id in self.players:
                player_dict = self.players[player.id]
                player_dict[player_points_key] += self.points[pp_play_key]
                player_dict[player_gp_key] += 1
            else:
                self.players[player.id] = {
                    player_points_key: self.points[pp_play_key],
                    player_gp_key: 1,
                    player_wins_key: 0
                }

    def _queue_full(self):
        return self.queue.qsize() >= team_size