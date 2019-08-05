import discord
import collections
import operator
import random
import datetime
import asyncio

from queue import Queue
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions

team_size = 6
minimum_game_time = 600 #Seconds (10 Minutes)
pp_play_key = "Play"
pp_win_key = "Win"
player_points_key = "Points"
player_gp_key = "GamesPlayed"
player_wins_key = "Wins"
queues_key = "Queues"

defaults = {"CategoryChannel": None, "Queues": {}, "GamesPlayed": 0, "Players": {}, "Scores": []}

class SixMans(commands.Cog):

    def __init__(self):
        self.config = Config.get_conf(self, identifier=1234567896, force_registration=True)
        self.config.register_guild(**defaults)
        self.queues = []
        self.games = []
        self.busy = False

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def loadQueues(self, ctx):
        await self._load_queues(ctx)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def addNewQueue(self, ctx, name, points_per_play: int, points_per_win: int, *channels):
        await self._pre_load_queues(ctx)
        queue_channels = []
        for channel in channels:
            queue_channels.append(await commands.TextChannelConverter().convert(ctx, channel))
        for queue in self.queues:
            if queue.name == name:
                await ctx.send(":x: There is already a queue set up with the name: {0}".format(name))
                return
            for channel in queue_channels:
                if channel in queue.channels:
                    await ctx.send(":x: {0} is already being used for queue: {1}".format(channel.mention, queue.name))
                    return

        points = {pp_play_key: points_per_play, pp_win_key: points_per_win}
        six_mans_queue = SixMansQueue(name, queue_channels, points, {}, 0)
        self.queues.append(six_mans_queue)
        await self._save_queues(ctx, self.queues)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def editQueue(self, ctx, current_name, new_name, points_per_play: int, points_per_win: int, *channels):
        await self._pre_load_queues(ctx)
        six_mans_queue = None
        for queue in self.queues:
            if queue.name == current_name:
                six_mans_queue = queue
                break

        if six_mans_queue is None:
            await ctx.send(":x: No queue found with name: {0}".format(current_name))
            return

        queue_channels = []
        for channel in channels:
            queue_channels.append(await commands.TextChannelConverter().convert(ctx, channel))
        for queue in self.queues:
            if queue.name == new_name:
                await ctx.send(":x: There is already a queue set up with the name: {0}".format(new_name))
                return
            for channel in queue_channels:
                if channel in queue.channels:
                    await ctx.send(":x: {0} is already being used for queue: {1}".format(channel.mention, queue.name))
                    return

        six_mans_queue.name = new_name
        six_mans_queue.points = {pp_play_key: points_per_play, pp_win_key: points_per_win}
        six_mans_queue.channels = queue_channels
        await self._save_queues(ctx, self.queues)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def removeQueue(self, ctx, *, queue_name):
        await self._pre_load_queues(ctx)
        for queue in self.queues:
            if queue.name == queue_name:
                self.queues.remove(queue)
                await self._save_queues(ctx, self.queues)
                await ctx.send("Done")
                return
        await ctx.send(":x: No queue set up with name: {0}".format(queue_name))

    @commands.guild_only()
    @commands.command(aliases=["qn"])
    async def getQueueNames(self, ctx):
        await self._pre_load_queues(ctx)
        queue_names = ""
        for queue in self.queues:
            queue_names += "{0}\n".format(queue.name)
        await ctx.send("```Queues set up in server:\n{0}```".format(queue_names))

    @commands.guild_only()
    @commands.command(aliases=["qi"])
    async def getQueueInfo(self, ctx, *, name):
        await self._pre_load_queues(ctx)
        for queue in self.queues:
            if queue.name.lower() == name.lower():
                await ctx.send(embed=self._format_queue_info(ctx, queue))
                return
        await ctx.send(":x: No queue set up with name: {0}".format(name))

    @commands.guild_only()
    @commands.command(aliases=["qa"])
    @checks.admin_or_permissions(manage_guild=True)
    async def queueAll(self, ctx, *members: discord.Member):
        """Mass queueing for testing purposes"""
        await self._pre_load_queues(ctx)
        six_mans_queue = self._get_queue(ctx)
        for member in members:
            if member in six_mans_queue.queue.queue:
                await ctx.send("{} is already in queue.".format(member.display_name))
                break
            six_mans_queue.queue.put(member)
            await ctx.send("{} added to queue. ({:d}/{:d})".format(member.display_name, six_mans_queue.queue.qsize(), team_size))
        if six_mans_queue._queue_full():
            await ctx.send("Queue is full! Teams are being created.")
            await self._randomize_teams(ctx, six_mans_queue)

    @commands.guild_only()
    @commands.command(aliases=["queue"])
    async def q(self, ctx):
        """Add yourself to the queue"""
        await self._pre_load_queues(ctx)
        six_mans_queue = self._get_queue(ctx)
        player = ctx.message.author

        if player in six_mans_queue.queue.queue:
            await ctx.send(":x: You are already in the {0} queue".format(six_mans_queue.name))
            return
        for game in self.games:
            if player in game:
                await ctx.send(":x: You are already in a game")
                return

        six_mans_queue.queue.put(player)

        await ctx.send("{0} added to {1} queue. ({2}/{3})".format(player.display_name, six_mans_queue.name,
            six_mans_queue.queue.qsize(), team_size))
        if six_mans_queue._queue_full():
            await ctx.send("**Queue is full! Teams are being created.**")
            await self._randomize_teams(ctx, six_mans_queue)

    @commands.guild_only()
    @commands.command(aliases=["dq"])
    async def dequeue(self, ctx):
        """Remove yourself from the queue"""
        await self._pre_load_queues(ctx)
        six_mans_queue = self._get_queue(ctx)
        player = ctx.message.author

        if player in six_mans_queue.queue:
            six_mans_queue.queue.remove(player)
            await ctx.send(
                "{0} removed from the {1} queue. ({2}/{3})".format(player.display_name, six_mans_queue.name,
                    six_mans_queue.queue.qsize(), team_size))
        else:
            await ctx.send(":x: You're not in the {0} queue".format(six_mans_queue.name))

    @commands.guild_only()
    @commands.command(aliases=["kq"])
    @checks.admin_or_permissions(manage_guild=True)
    async def kickQueue(self, ctx, player: discord.Member):
        """Remove someone else from the queue"""
        await self._pre_load_queues(ctx)
        six_mans_queue = self._get_queue(ctx)
        if player in six_mans_queue.queue:
            six_mans_queue.queue.remove(player)
            await ctx.send(
                "{} removed from queue. ({:d}/{:d})".format(player.display_name, six_mans_queue.queue.qsize(), team_size))
        else:
            await ctx.send("{} is not in queue.".format(player.display_name))

    @commands.guild_only()
    @commands.command(aliases=["cg"])
    async def cancelGame(self, ctx):
        """Cancel the current 6Mans game. Can only be used in a 6Mans game channel.
        The game will end with no points given to any of the players. The players with then be allowed to queue again."""
        await self._pre_load_queues(ctx)
        game = self._get_game(ctx)
        six_mans_queue = None
        for queue in self.queues:
            if queue.name == game.queueName:
                six_mans_queue = queue

        if six_mans_queue is None:
            await ctx.send(":x: Queue not found for this channel, please message an Admin if you think this is a mistake.")
            return

        opposing_captain = None
        if ctx.author in game.blue:
            opposing_captain = game.captains[1] #Orange team captain
        elif ctx.author in game.orange:
            opposing_captain = game.captains[0] #Blue team captain

        if opposing_captain is None:
            await ctx.send(":x: Only players on one of the two teams can cancel the game.")
            return

        msg = await ctx.send("{0} Please verify that both teams want to cancel the game.".format(opposing_captain.mention))
        start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)

        pred = ReactionPredicate.yes_or_no(msg, opposing_captain)
        await ctx.bot.wait_for("reaction_add", check=pred)
        if pred.result is True:
        # User responded with tick
            self.games.remove(game)
            await ctx.send("Done. Feel free to queue again in an appropriate channel.\n**This channel will be deleted in 30 seconds**")
            await asyncio.sleep(30)
            await ctx.channel.delete()
        else:
        # User responded with cross
            await ctx.send(":x: Cancel not verified. To cancel the game you will need to use the `cg` command again.")

    @commands.guild_only()
    @commands.command(aliases=["sr"])
    async def scoreReport(self, ctx, winning_team):
        """Report which team won the series. Can only be used in a 6Mans game channel.
        Only valid after 10 minutes have passed since the game started. Both teams will need to verify the results.

        `winning_team` must be either `Blue` or `Orange`"""
        await self._pre_load_queues(ctx)
        game_time = ctx.message.created_at - ctx.channel.created_at
        if game_time.seconds < minimum_game_time:
            await ctx.send(":x: You can't report a game outcome until at least **10 minutes** have passed since the game was created."
                "\nCurrent time that's passed = **{0} minute(s)**".format(game_time.seconds // 60))
            return

        if winning_team.lower() != "blue" and winning_team.lower() != "orange":
            await ctx.send(":x: {0} is an invalid input for `winning_team`. Must be either `Blue` or `Orange`".format(winning_team))
            return

        game = self._get_game(ctx)
        if game.scoreReported == True:
            await ctx.send(":x: Someone has already reported the results or is waiting for verification")
            return

        six_mans_queue = None
        for queue in self.queues:
            if queue.name == game.queueName:
                six_mans_queue = queue

        if six_mans_queue is None:
            await ctx.send(":x: Queue not found for this channel, please message an Admin if you think this is a mistake.")
            return

        opposing_captain = None
        if ctx.author in game.blue:
            opposing_captain = game.captains[1] #Orange team captain
        elif ctx.author in game.orange:
            opposing_captain = game.captains[0] #Blue team captain

        if opposing_captain is None:
            await ctx.send(":x: Only players on one of the two teams can report the score")
            return

        msg = await ctx.send("{0} Please verify that the **{1}** team won the series".format(opposing_captain.mention, winning_team))
        start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)

        game.scoreReported = True
        pred = ReactionPredicate.yes_or_no(msg, opposing_captain)
        await ctx.bot.wait_for("reaction_add", check=pred)
        if pred.result is True:
        # User responded with tick
            pass
        else:
        # User responded with cross
            game.scoreReported = False
            await ctx.send(":x: Score report not verified. To report the score you will need to use the `sr` command again.")
            return

        winning_players = []
        losing_players = []
        if winning_team.lower() == "blue":
            winning_players = game.blue
            losing_players = game.orange
        else:
            winning_players = game.orange
            losing_players = game.blue

        _scores = await self._scores(ctx)
        _players = await self._players(ctx)
        _games_played = await self._games_played(ctx)
        date_time = datetime.datetime.now().strftime("%d-%b-%Y (%H:%M:%S.%f)")
        for player in winning_players:
            score = self._create_player_score(six_mans_queue, player, 1, date_time)
            self._give_points(six_mans_queue.players, score)
            self._give_points(_players, score)
            _scores.insert(0, score)
        for player in losing_players:
            score = self._create_player_score(six_mans_queue, player, 0, date_time)
            self._give_points(six_mans_queue.players, score)
            self._give_points(_players, score)
            _scores.insert(0, score)

        _games_played += 1
        six_mans_queue.gamesPlayed += 1

        await self._save_scores(ctx, _scores)
        await self._save_queues(ctx, self.queues)
        await self._save_players(ctx, _players)
        await self._save_games_played(ctx, _games_played)

        self.games.remove(game)
        await ctx.send("Done. Thanks for playing!\n**This channel and the team voice channels will be deleted in 30 seconds**")
        await asyncio.sleep(30)
        await ctx.channel.delete()
        for vc in game.voiceChannels:
            await vc.delete()

    @commands.guild_only()
    @commands.command(aliases=["qlb"])
    async def queueLeaderBoard(self, ctx, *, queue_name: str = None):
        """Get the top ten players in points for the specific queue. If no queue name is given the list will be the top ten players across all queues.
        If you're not in the top ten your name and rank will be shown at the bottom of the list."""
        await self._pre_load_queues(ctx)
        players = None
        six_mans_queue = None
        if queue_name is not None:
            for queue in self.queues:
                if queue.name.lower() == queue_name.lower():
                    six_mans_queue = queue
                    players = queue.players
        else:
            players = await self._players(ctx)

        if players is None or players == {}:
            await ctx.send(":x: Queue leaderboard not available for queue with name: {0}".format(queue_name))
            return

        sorted_players = sorted(players.items(), key=lambda x: x[1][player_wins_key], reverse=True)
        sorted_players = sorted(sorted_players, key=lambda x: x[1][player_points_key], reverse=True)
        await ctx.send(embed=await self._format_leaderboard(ctx, sorted_players, six_mans_queue))

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

    def _give_points(self, players_dict, score):
        player_id = score["Player"]
        points_earned = score["Points"]
        win = score["Win"]

        player_dict = players_dict.setdefault("{0}".format(player_id), {})
        player_dict[player_points_key] = player_dict.get(player_points_key, 0) + points_earned
        player_dict[player_gp_key] = player_dict.get(player_gp_key, 0) + 1
        player_dict[player_wins_key] = player_dict.get(player_wins_key, 0) + win

    def _create_player_score(self, six_mans_queue, player, win, date_time):
        points_dict = six_mans_queue.points
        if win:
            points_earned = points_dict[pp_play_key] + points_dict[pp_win_key]
        else:
            points_earned = points_dict[pp_play_key]
        return {
            "Queue": six_mans_queue.name,
            "Player": player.id,
            "Win": win,
            "Points": points_earned,
            "DateTime": date_time
        }

    async def _format_leaderboard(self, ctx, sorted_players, six_mans_queue):
        if six_mans_queue is None:
            queue_name = ctx.guild.name
            games_played = await self._games_played(ctx)
        else:
            queue_name = six_mans_queue.name
            games_played = six_mans_queue.gamesPlayed
        
        embed = discord.Embed(title="{0} 6 Mans Leaderboard".format(queue_name), color=discord.Colour.blue())
        embed.add_field(name="Games Played", value="{}\n".format(games_played), inline=True)
        embed.add_field(name="Unique Players All-Time", value="{}\n".format(len(sorted_players)), inline=True)
        
        index = 1
        message = ""
        for player in sorted_players:
            try:
                member = await commands.MemberConverter().convert(ctx, player[0])
            except:
                await ctx.send(":x: Can't find player with id: {}".format(player[0]))
                return
            player_info = player[1]
            message += "`{0}` {1} **Points:** {2}  **Wins:** {3}  **Games Played:** {4}\n".format(index, member.mention, player_info[player_points_key], 
                player_info[player_wins_key], player_info[player_gp_key])
            index += 1
            if index > 10:
                break
        
        author = ctx.author
        try:
            author_index = [y[0] for y in sorted_players].index("{0}".format(author.id))
            if author_index is not None and author_index > 10:
                author_info = sorted_players[author_index][1]
                message += "\n\n`{0}` {1} **Points:** {2}  **Wins:** {3}  **Games Played:** {4}".format(author_index + 1, author.mention, author_info[player_points_key], 
                    author_info[player_wins_key], author_info[player_gp_key])
        except Exception:
            pass

        embed.add_field(name="Most Points in {0}".format(queue_name), value=message, inline=False)
        return embed

    async def _randomize_teams(self, ctx, six_mans_queue):
        self.busy = True
        game = await self._create_game(ctx, six_mans_queue)
        for player in game.players:
            for queue in self.queues:
                if player in queue.queue:
                    queue.queue.remove(player)

        orange = random.sample(game.players, 3)
        for player in orange:
            game.add_to_orange(player)
            await game.voiceChannels[1].set_permissions(player, connect=True)
        
        blue = list(game.players)
        for player in blue:
            game.add_to_blue(player)
            await game.voiceChannels[0].set_permissions(player, connect=True)

        game.reset_players()
        game.get_new_captains_from_teams()

        await self._display_game_info(ctx, game, six_mans_queue)

        self.games.append(game)

        self.busy = False

    async def _display_game_info(self, ctx, game, six_mans_queue):
        await game.text_channel.send("{}\n".format(", ".join([player.mention for player in game.players])))
        embed = discord.Embed(title="{0} 6 Mans Game Info".format(six_mans_queue.name), color=discord.Colour.blue())
        embed.add_field(name="Blue Team", value="{}\n".format(", ".join([player.mention for player in game.blue])), inline=False)
        embed.add_field(name="Orange Team", value="{}\n".format(", ".join([player.mention for player in game.orange])), inline=False)
        embed.add_field(name="Captains", value="**Blue:** {0}\n**Orange:** {1}".format(game.captains[0].mention, game.captains[1].mention), inline=False)
        embed.add_field(name="Lobby Info", value="**Username:** {0}\n**Password:** {1}".format(game.roomName, game.roomPass), inline=False)
        embed.add_field(name="Point Breakdown", value="**Playing:** {0}\n**Winning Bonus:** {1}"
            .format(six_mans_queue.points[pp_play_key], six_mans_queue.points[pp_win_key]), inline=False)
        embed.add_field(name="Additional Info", value="Feel free to play whatever type of series you want, whether a bo3, bo5, or any other.\n\n"
            "When you are done playing with the current teams please report the winning team using the command `{0}sr [winning_team]` where "
            "the `winning_team` parameter is either `Blue` or `Orange`. Both teams will need to verify the results.\n\nIf you wish to cancel "
            "the game and allow players to queue again you can use the `{0}cg` command. Both teams will need to verify that they wish to "
            "cancel the game.".format(ctx.prefix), inline=False)
        embed.add_field(name="Help", value="If you need any help or have questions please contact an Admin. "
            "If you think the bot isn't working correctly or have suggestions to improve it, please contact adammast.", inline=False)
        await game.text_channel.send(embed=embed)

    async def _create_game(self, ctx, six_mans_queue):
        players = [six_mans_queue.queue.get() for _ in range(team_size)]
        text_channel, voice_channels = await self._create_game_channels(ctx, six_mans_queue)
        for player in players:
            await text_channel.set_permissions(player, read_messages=True)
        return Game(players, text_channel, voice_channels, six_mans_queue.name)

    async def _create_game_channels(self, ctx, six_mans_queue):
        guild = ctx.message.guild
        text_channel = await guild.create_text_channel(six_mans_queue.name, 
            overwrites= {
                guild.default_role: discord.PermissionOverwrite(read_messages=False)
            },
            category= await self._category(ctx))
        voice_channels = [
            await guild.create_voice_channel("{0} 6 Mans Blue Team".format(six_mans_queue.name), 
                overwrites= {
                    guild.default_role: discord.PermissionOverwrite(connect=False)
                },
                category= await self._category(ctx)),
            await guild.create_voice_channel("{0} 6 Mans Orange Team".format(six_mans_queue.name), 
                overwrites= {
                    guild.default_role: discord.PermissionOverwrite(connect=False)
                },
                category= await self._category(ctx))
        ]
        return text_channel, voice_channels

    def _get_game(self, ctx):
        for game in self.games:
            if game.text_channel == ctx.channel:
                return game

    def _get_queue(self, ctx):
        for six_mans_queue in self.queues:
            for channel in six_mans_queue.channels:
                if channel == ctx.channel:
                    return six_mans_queue

    def _format_queue_info(self, ctx, queue):
        embed = discord.Embed(title="{0} Info".format(queue.name), color=discord.Colour.blue())
        embed.add_field(name="Channels", value="{}\n".format(", ".join([channel.mention for channel in queue.channels])), inline=False)
        embed.add_field(name="Games Played", value="{}\n".format(queue.gamesPlayed), inline=False)
        embed.add_field(name="Unique Players All-Time", value="{}\n".format(len(queue.players)), inline=False)
        embed.add_field(name="Point Breakdown", value="**Per Series Played:** {0}\n**Per Series Win:** {1}"
            .format(queue.points[pp_play_key], queue.points[pp_win_key]), inline=False)
        return embed

    async def _pre_load_queues(self, ctx):
        if self.queues is None or self.queues == []:
            await self._load_queues(ctx)

    async def _load_queues(self, ctx):
        queues = await self._queues(ctx)
        self.queues = []
        for key, value in queues.items():
            queue_channels = []
            for channel in value["Channels"]:
                queue_channels.append(ctx.guild.get_channel(channel))
            for queue in self.queues:
                if queue.name == key:
                    await ctx.send(":x: There is already a queue set up with the name: {0}".format(queue.name))
                    return
                for channel in queue_channels:
                    if channel in queue.channels:
                        await ctx.send(":x: {0} is already being used for queue: {1}".format(channel.mention, queue.name))
                        return

            self.queues.append(SixMansQueue(key, queue_channels, value["Points"], value["Players"], value["GamesPlayed"]))

    async def _queues(self, ctx):
        return await self.config.guild(ctx.guild).Queues()

    async  def _save_queues(self, ctx, queues):
        queue_dict = {}
        for queue in queues:
            queue_dict[queue.name] = queue._to_dict()
        await self.config.guild(ctx.guild).Queues.set(queue_dict)

    async def _scores(self, ctx):
        return await self.config.guild(ctx.guild).Scores()

    async def _save_scores(self, ctx, scores):
        await self.config.guild(ctx.guild).Scores.set(scores)

    async def _games_played(self, ctx):
        return await self.config.guild(ctx.guild).GamesPlayed()

    async def _save_games_played(self, ctx, games_played):
        await self.config.guild(ctx.guild).GamesPlayed.set(games_played)

    async def _players(self, ctx):
        return await self.config.guild(ctx.guild).Players()

    async def _save_players(self, ctx, players):
        await self.config.guild(ctx.guild).Players.set(players)

    async def _category(self, ctx):
        return ctx.guild.get_channel(await self.config.guild(ctx.guild).CategoryChannel())

    async def _save_category(self, ctx, category):
        await self.config.guild(ctx.guild).CategoryChannel.set(category)

class Game:
    def __init__(self, players, text_channel, voice_channels, queue_name):
        self.players = set(players)
        self.captains = list(random.sample(self.players, 2))
        self.orange = set()
        self.blue = set()
        self.roomName = self._generate_name_pass()
        self.roomPass = self._generate_name_pass()
        self.textChannel = text_channel
        self.voiceChannels = voice_channels #List of voice channels: [Blue, Orange]
        self.queueName = queue_name
        self.scoreReported = False

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
        self.captains = []
        self.captains.append(list(self.blue)[0])
        self.captains.append(list(self.orange)[0])

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

    def _queue_full(self):
        return self.queue.qsize() >= team_size

    def _to_dict(self):
        channel_ids = []
        for channel in self.channels:
            channel_ids.append(channel.id)
        return {
            "Channels": channel_ids,
            "Points": self.points,
            "Players": self.players,
            "GamesPlayed": self.gamesPlayed
        }