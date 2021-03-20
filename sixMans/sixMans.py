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

team_size = 6
minimum_game_time = 600 #Seconds (10 Minutes)
player_timeout_time = 14400 #How long players can be in a queue in seconds (4 Hours)
loop_time = 5 #How often to check the queues in seconds
verify_timeout = 15
pp_play_key = "Play"
pp_win_key = "Win"
player_points_key = "Points"
player_gp_key = "GamesPlayed"
player_wins_key = "Wins"
queues_key = "Queues"

defaults = {"CategoryChannel": None, "HelperRole": None, "AutoMove": False, "QLobby": None, "Games": {}, "Queues": {}, "GamesPlayed": 0, "Players": {}, "Scores": []}

class SixMans(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567896, force_registration=True)
        self.config.register_guild(**defaults)
        self.queues = []
        self.games = []
        self.task = self.bot.loop.create_task(self.timeout_queues())
        self.SHUFFLE_REACT = "\U0001F500" # :twisted_rightwards_arrows:
        self.WHITE_X_REACT = "\U0000274E" # :negative_squared_cross_mark:
        self.WHITE_CHECK_REACT = "\U00002705" # :white_check_mark:


    def cog_unload(self):
        """Clean up when cog shuts down."""
        if self.task:
            self.task.cancel()

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def loadGames(self, ctx):
        await self._pre_load_queues(ctx)
        msg = await ctx.send("{0} Please verify that you wish to reload the games.".format(ctx.author.mention))
        start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)

        pred = ReactionPredicate.yes_or_no(msg, ctx.author)
        await ctx.bot.wait_for("reaction_add", check=pred)
        if pred.result is True:
            await self._pre_load_games(ctx, True)
            await ctx.send("Done")
        else:
            await ctx.send(":x: Games **not** reloaded.")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearSixMansData(self, ctx):
        msg = await ctx.send("{0} Please verify that you wish to clear **all** of the 6 Mans data.".format(ctx.author.mention))
        start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)

        pred = ReactionPredicate.yes_or_no(msg, ctx.author)
        await ctx.bot.wait_for("reaction_add", check=pred)
        if pred.result is True:
            await self.config.clear_all_guilds()
            await ctx.send("Done")
        else:
            await ctx.send(":x: Data **not** cleared.")

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
        six_mans_queue = SixMansQueue(name, ctx.guild, queue_channels, points, {}, 0)
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
            if queue.name != current_name:
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
            if queue.guild == ctx.guild:
                queue_names += "{0}\n".format(queue.name)
        await ctx.send("```Queues set up in server:\n{0}```".format(queue_names))

    @commands.guild_only()
    @commands.command(aliases=["qi"])
    async def getQueueInfo(self, ctx, *, queue_name=None):
        await self._pre_load_queues(ctx)
        if queue_name is not None:
            for queue in self.queues:
                if queue.name.lower() == queue_name.lower():
                    await ctx.send(embed=self._format_queue_info(ctx, queue))
                    return
            await ctx.send(":x: No queue set up with name: {0}".format(queue_name))
            return

        six_mans_queue = self._get_queue(ctx)
        if six_mans_queue is None:
            await ctx.send(":x: No queue set up in this channel")
            return
        
        await ctx.send(embed=self._format_queue_info(ctx, six_mans_queue))

    @commands.guild_only()
    @commands.command(aliases=["cq", "status"])
    async def checkQueue(self, ctx):
        await self._pre_load_queues(ctx)
        six_mans_queue = self._get_queue(ctx)
        if six_mans_queue is None:
            await ctx.send(":x: No queue set up in this channel")
            return
        
        await ctx.send(embed=self._format_queue(ctx, six_mans_queue))

    @commands.guild_only()
    @commands.command(aliases=["setQueueLobby"])
    @checks.admin_or_permissions(manage_guild=True)
    async def setQLobby(self, ctx, lobby_voice: discord.VoiceChannel):
        await self._save_q_lobby_vc(ctx, lobby_voice.id)
        await ctx.send("Done")
    
    @commands.guild_only()
    @commands.command(aliases=["unsetQueueLobby, unsetQLobby"])
    @checks.admin_or_permissions(manage_guild=True)
    async def clearQLobby(self, ctx):
        await self._save_q_lobby_vc(ctx, None)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command(aliases=["smMove", "moveme"])
    async def moveMe(self, ctx):
        if ctx.message.channel.category != await self._category(ctx):
            return False

        game = self._get_game(ctx)
        player = ctx.message.author
        if game:
            try:
                if player in game.blue:
                    await player.move_to(game.voiceChannels[0])
                if player in game.orange:
                    await player.move_to(game.voiceChannels[1])
                await ctx.message.add_reaction("\U00002705") # white_check_mark
            except:
                await ctx.message.add_reaction("\U0000274E") # negative_squared_cross_mark
                if not player.voice:
                    await ctx.send("{}, you must be connected to a voice channel to be moved to your Six Man's team channel.".format(player.mention))
        else:
            await ctx.message.add_reaction("\U0000274E") # negative_squared_cross_mark
            await ctx.send("{}, you must run this command from within your queue lobby channel.".format(player.mention))
            # TODO: determine a workaround from filtering through all active games

    @commands.guild_only()
    @commands.command(aliases=["qa"])
    @checks.admin_or_permissions(manage_guild=True)
    async def queueAll(self, ctx, *members: discord.Member):
        """Mass queueing for testing purposes"""
        await self._pre_load_queues(ctx)
        await self._pre_load_games(ctx, False)
        six_mans_queue = self._get_queue(ctx)
        for member in members:
            if member in six_mans_queue.queue.queue:
                await ctx.send("{} is already in queue.".format(member.display_name))
                break
            await self._add_to_queue(member, six_mans_queue)
        if six_mans_queue._queue_full():
            await self._select_teams(ctx, six_mans_queue)

    @commands.guild_only()
    @commands.command(aliases=["queue"])
    async def q(self, ctx):
        """Add yourself to the queue"""
        await self._pre_load_queues(ctx)
        await self._pre_load_games(ctx, False)
        six_mans_queue = self._get_queue(ctx)
        player = ctx.message.author

        if player in six_mans_queue.queue.queue:
            await ctx.send(":x: You are already in the {0} queue".format(six_mans_queue.name))
            return
        for game in self.games:
            if player in game:
                await ctx.send(":x: You are already in a game")
                return

        await self._add_to_queue(player, six_mans_queue)
        if six_mans_queue._queue_full():
            await self._select_teams(ctx, six_mans_queue)

    @commands.guild_only()
    @commands.command(aliases=["dq", "lq", "leaveq", "leaveQ", "unqueue", "unq", "uq"])
    async def dequeue(self, ctx):
        """Remove yourself from the queue"""
        await self._pre_load_queues(ctx)
        six_mans_queue = self._get_queue(ctx)
        player = ctx.message.author

        if player in six_mans_queue.queue:
            await self._remove_from_queue(player, six_mans_queue)
        else:
            await ctx.send(":x: You're not in the {0} queue".format(six_mans_queue.name))

    @commands.guild_only()
    @commands.command(aliases=["kq"])
    async def kickQueue(self, ctx, player: discord.Member):
        """Remove someone else from the queue"""
        if not await self.has_perms(ctx):
            return

        await self._pre_load_queues(ctx)
        six_mans_queue = self._get_queue(ctx)
        if player in six_mans_queue.queue:
            await self._remove_from_queue(player, six_mans_queue)
        else:
            await ctx.send("{} is not in queue.".format(player.display_name))

    @commands.guild_only()
    @commands.command(aliases=["cg"])
    async def cancelGame(self, ctx):
        """Cancel the current 6Mans game. Can only be used in a 6Mans game channel.
        The game will end with no points given to any of the players. The players with then be allowed to queue again."""
        await self._pre_load_queues(ctx)
        await self._pre_load_games(ctx, False)
        game, six_mans_queue = await self._get_info(ctx)
        if game is None or six_mans_queue is None:
            return

        opposing_captain = self._get_opposing_captain(ctx, game)
        if opposing_captain is None:
            await ctx.send(":x: Only players on one of the two teams can cancel the game.")
            return

        msg = await ctx.send("{0} Please verify that both teams want to cancel the game. You have {1} seconds to verify".format(opposing_captain.mention, verify_timeout))
        start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)

        pred = ReactionPredicate.yes_or_no(msg, opposing_captain)
        try:
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=verify_timeout)
            if pred.result is True:
                await ctx.send("Done. Feel free to queue again in an appropriate channel.\n**This channel will be deleted in 30 seconds**")
                await self._remove_game(ctx, game)
            else:
                await ctx.send(":x: Cancel not verified. To cancel the game you will need to use the `{0}cg` command again.".format(ctx.prefix))
        except asyncio.TimeoutError:
            self._swap_opposing_captain(game, opposing_captain)
            await ctx.send(":x: Cancel not verified in time. To cancel the game you will need to use the `{0}cg` command again."
                "\n**If one of the captains is afk, have someone from that team use the command.**".format(ctx.prefix))

    @commands.guild_only()
    @commands.command(aliases=["fcg"])
    async def forceCancelGame(self, ctx, gameId: int = None):
        """Cancel the current 6Mans game. Can only be used in a 6Mans game channel unless a gameId is given.
        The game will end with no points given to any of the players. The players with then be allowed to queue again."""
        if not await self.has_perms(ctx):
            return
        
        await self._pre_load_queues(ctx)
        await self._pre_load_games(ctx, False)
        game = None
        if gameId is None:
            game, six_mans_queue = await self._get_info(ctx)
            if game is None or six_mans_queue is None:
                return
        else:
            for active_game in self.games:
                if active_game.id == gameId:
                    game = active_game

        if not game:
            await ctx.send("No game found with id: {}".format(gameId))
            return

        msg = await ctx.send("{0} Please verify that you want to cancel this game.".format(ctx.author.mention))
        start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)

        game.scoreReported = True
        pred = ReactionPredicate.yes_or_no(msg, ctx.author)
        try:
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=verify_timeout)
            if pred.result is True:
                await ctx.send("Done.")
                try:
                    # If the text channel has been deleted this will throw an error and we'll instead want to send the message to wherever the command was used
                    await game.textChannel.send("Game canceled by {}. Feel free to queue again in an appropriate channel.\n**This game's channels will be deleted in 30 seconds**".format(ctx.author.mention))
                except:
                    await ctx.send("Game canceled by {}. Feel free to queue again in an appropriate channel.\n**This game's channels will be deleted in 30 seconds**".format(ctx.author.mention))
                await self._remove_game(ctx, game)
            else:
                await ctx.send(":x: Cancel not verified. To cancel the game you will need to use the `{0}cg` command again.".format(ctx.prefix))
        except asyncio.TimeoutError:
            await ctx.send(":x: Cancel not verified in time. To cancel the game you will need to use the `{0}cg` command again.".format(ctx.prefix))   

    @commands.guild_only()
    @commands.command(aliases=["fr"])
    async def forceResult(self, ctx, winning_team):
        if not await self.has_perms(ctx):
            return

        await self._pre_load_queues(ctx)
        await self._pre_load_games(ctx, False)
        if winning_team.lower() != "blue" and winning_team.lower() != "orange":
            await ctx.send(":x: {0} is an invalid input for `winning_team`. Must be either `Blue` or `Orange`".format(winning_team))
            return

        game, six_mans_queue = await self._get_info(ctx)
        if game is None or six_mans_queue is None:
            return

        msg = await ctx.send("{0} Please verify that the **{1}** team won the series.".format(ctx.author.mention, winning_team))
        start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)

        game.scoreReported = True
        pred = ReactionPredicate.yes_or_no(msg, ctx.author)
        await ctx.bot.wait_for("reaction_add", check=pred)
        if pred.result is True:
            pass
        else:
            game.scoreReported = False
            await ctx.send(":x: Score report not verified. To report the score you will need to use the `{0}sr` command again.".format(ctx.prefix))
            return

        await ctx.send("Done. Thanks for playing!\n**This channel and the team voice channels will be deleted in 30 seconds**")
        await self._finish_game(ctx, game, six_mans_queue, winning_team)

    @commands.guild_only()
    @commands.command(aliases=["sr"])
    async def scoreReport(self, ctx, winning_team):
        """Report which team won the series. Can only be used in a 6Mans game channel.
        Only valid after 10 minutes have passed since the game started. Both teams will need to verify the results.

        `winning_team` must be either `Blue` or `Orange`"""
        await self._pre_load_queues(ctx)
        await self._pre_load_games(ctx, False)
        game_time = ctx.message.created_at - ctx.channel.created_at
        if game_time.seconds < minimum_game_time:
            await ctx.send(":x: You can't report a game outcome until at least **10 minutes** have passed since the game was created."
                "\nCurrent time that's passed = **{0} minute(s)**".format(game_time.seconds // 60))
            return

        if winning_team.lower() != "blue" and winning_team.lower() != "orange":
            await ctx.send(":x: {0} is an invalid input for `winning_team`. Must be either `Blue` or `Orange`".format(winning_team))
            return

        game, six_mans_queue = await self._get_info(ctx)
        if game is None or six_mans_queue is None:
            return

        if game.scoreReported == True:
            await ctx.send(":x: Someone has already reported the results or is waiting for verification")
            return

        opposing_captain = self._get_opposing_captain(ctx, game)
        if opposing_captain is None:
            await ctx.send(":x: Only players on one of the two teams can report the score")
            return

        msg = await ctx.send("{0} Please verify that the **{1}** team won the series. You have {2} seconds to verify"
            .format(opposing_captain.mention, winning_team, verify_timeout))
        start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)

        game.scoreReported = True
        pred = ReactionPredicate.yes_or_no(msg, opposing_captain)
        try:
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=verify_timeout)
            if pred.result is True:
                pass
            else:
                game.scoreReported = False
                await ctx.send(":x: Score report not verified. To report the score you will need to use the `{0}sr` command again.".format(ctx.prefix))
                return
        except asyncio.TimeoutError:
            game.scoreReported = False
            self._swap_opposing_captain(game, opposing_captain)
            await ctx.send(":x: Score report not verified in time. To report the score you will need to use the `{0}sr` command again."
                "\n**If one of the captains is afk, have someone from that team use the command.**".format(ctx.prefix))
            return

        await ctx.send("Done. Thanks for playing!\n**This channel and the team voice channels will be deleted in 30 seconds**")
        await self._finish_game(ctx, game, six_mans_queue, winning_team)

    @commands.guild_only()
    @commands.group(aliases=["qlb"])
    async def queueLeaderBoard(self, ctx):
        """Get the top ten players in points for the specific queue. If no queue name is given the list will be the top ten players across all queues.
        If you're not in the top ten your name and rank will be shown at the bottom of the list."""

    @commands.guild_only()
    @queueLeaderBoard.command(aliases=["all-time", "alltime"])
    async def overall(self, ctx, *, queue_name: str = None):
        """All-time leader board"""
        await self._pre_load_queues(ctx)
        players = None
        if queue_name is not None:
            for queue in self.queues:
                if queue.name.lower() == queue_name.lower():
                    queue_name = queue.name
                    players = queue.players
                    games_played = queue.gamesPlayed
        else:
            players = await self._players(ctx)
            queue_name = ctx.guild.name
            games_played = await self._games_played(ctx)

        if players is None or players == {}:
            await ctx.send(":x: Queue leaderboard not available for {0}".format(queue_name))
            return

        sorted_players = self._sort_player_dict(players)
        await ctx.send(embed=await self._format_leaderboard(ctx, sorted_players, queue_name, games_played, "All-time"))

    @commands.guild_only()
    @queueLeaderBoard.command(aliases=["daily"])
    async def day(self, ctx, *, queue_name: str = None):
        """Daily leader board. All games from the last 24 hours will count"""
        await self._pre_load_queues(ctx)
        scores = await self._scores(ctx)

        queue_id = self._get_queue_id_by_name(queue_name)
        day_ago = datetime.datetime.now() - datetime.timedelta(days=1)
        players, games_played = self._filter_scores(scores, day_ago, queue_id)

        if players is None or players == {}:
            await ctx.send(":x: Queue leaderboard not available for {0}".format(queue_name))
            return

        queue_name = self._get_queue_name(ctx, queue_name)
        sorted_players = self._sort_player_dict(players)
        await ctx.send(embed=await self._format_leaderboard(ctx, sorted_players, queue_name, games_played, "Daily"))

    @commands.guild_only()
    @queueLeaderBoard.command(aliases=["weekly", "wk"])
    async def week(self, ctx, *, queue_name: str = None):
        """Weekly leader board. All games from the last week will count"""
        await self._pre_load_queues(ctx)
        scores = await self._scores(ctx)

        queue_id = self._get_queue_id_by_name(queue_name)
        week_ago = datetime.datetime.now() - datetime.timedelta(weeks=1)
        players, games_played = self._filter_scores(scores, week_ago, queue_id)

        if players is None or players == {}:
            await ctx.send(":x: Queue leaderboard not available for {0}".format(queue_name))
            return

        queue_name = self._get_queue_name(ctx, queue_name)
        sorted_players = self._sort_player_dict(players)
        await ctx.send(embed=await self._format_leaderboard(ctx, sorted_players, queue_name, games_played, "Weekly"))

    @commands.guild_only()
    @queueLeaderBoard.command(aliases=["monthly", "mnth"])
    async def month(self, ctx, *, queue_name: str = None):
        """Monthly leader board. All games from the last 30 days will count"""
        await self._pre_load_queues(ctx)
        scores = await self._scores(ctx)

        queue_id = self._get_queue_id_by_name(queue_name)
        month_ago = datetime.datetime.now() - datetime.timedelta(days=30)
        players, games_played = self._filter_scores(scores, month_ago, queue_id)

        if players is None or players == {}:
            await ctx.send(":x: Queue leaderboard not available for {0}".format(queue_name))
            return

        queue_name = self._get_queue_name(ctx, queue_name)
        sorted_players = self._sort_player_dict(players)
        await ctx.send(embed=await self._format_leaderboard(ctx, sorted_players, queue_name, games_played, "Monthly"))

    @commands.guild_only()
    @commands.group(aliases=["rnk"])
    async def rank(self, ctx):
        """Get your rank in points, wins, and games played for the specific queue. If no queue name is given it will show your overall rank across all queues."""

    @commands.guild_only()
    @rank.command(aliases=["all-time", "overall"])
    async def alltime(self, ctx, player: discord.Member = None, *, queue_name: str = None):
        """All-time ranks"""
        await self._pre_load_queues(ctx)
        players = None
        if queue_name is not None:
            for queue in self.queues:
                if queue.name.lower() == queue_name.lower():
                    queue_name = queue.name
                    players = queue.players
        else:
            players = await self._players(ctx)
            queue_name = ctx.guild.name

        if players is None or players == {}:
            await ctx.send(":x: Player ranks not available for {0}".format(queue_name))
            return

        sorted_players = self._sort_player_dict(players)
        player = player if player else ctx.author
        await ctx.send(embed=self._format_rank(ctx, player, sorted_players, queue_name, "All-time"))

    @commands.guild_only()
    @rank.command(aliases=["day"])
    async def daily(self, ctx, player: discord.Member = None, *, queue_name: str = None):
        """Daily ranks. All games from the last 24 hours will count"""
        await self._pre_load_queues(ctx)
        scores = await self._scores(ctx)

        queue_id = self._get_queue_id_by_name(queue_name)
        day_ago = datetime.datetime.now() - datetime.timedelta(days=1)
        players = self._filter_scores(scores, day_ago, queue_id)[0]

        if players is None or players == {}:
            await ctx.send(":x: Player ranks not available for {0}".format(queue_name))
            return

        queue_name = self._get_queue_name(ctx, queue_name)
        sorted_players = self._sort_player_dict(players)
        player = player if player else ctx.author
        await ctx.send(embed=self._format_rank(ctx, player, sorted_players, queue_name, "Daily"))

    @commands.guild_only()
    @rank.command(aliases=["week", "wk"])
    async def weekly(self, ctx, player: discord.Member = None, *, queue_name: str = None):
        """Weekly ranks. All games from the last week will count"""
        await self._pre_load_queues(ctx)
        scores = await self._scores(ctx)

        queue_id = self._get_queue_id_by_name(queue_name)
        week_ago = datetime.datetime.now() - datetime.timedelta(weeks=1)
        players = self._filter_scores(scores, week_ago, queue_id)[0]

        if players is None or players == {}:
            await ctx.send(":x: Player ranks not available for {0}".format(queue_name))
            return

        queue_name = self._get_queue_name(ctx, queue_name)
        sorted_players = self._sort_player_dict(players)
        player = player if player else ctx.author
        await ctx.send(embed=self._format_rank(ctx, player, sorted_players, queue_name, "Weekly"))

    @commands.guild_only()
    @rank.command(aliases=["month", "mnth"])
    async def monthly(self, ctx, player: discord.Member = None, *, queue_name: str = None):
        """Monthly ranks. All games from the last 30 days will count"""
        await self._pre_load_queues(ctx)
        scores = await self._scores(ctx)

        queue_id = self._get_queue_id_by_name(queue_name)
        month_ago = datetime.datetime.now() - datetime.timedelta(days=30)
        players = self._filter_scores(scores, month_ago, queue_id)[0]

        if players is None or players == {}:
            await ctx.send(":x: Player ranks not available for {0}".format(queue_name))
            return

        queue_name = self._get_queue_name(ctx, queue_name)
        sorted_players = self._sort_player_dict(players)
        player = player if player else ctx.author
        await ctx.send(embed=self._format_rank(ctx, player, sorted_players, queue_name, "Monthly"))

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def toggleAutoMove(self, ctx):
        """Toggle whether or not bot moves members to their assigned 6-mans team voice channel"""
        new_automove_status = not await self._get_automove(ctx)
        await self._save_automove(ctx, new_automove_status)

        action = "will move" if new_automove_status else "will not move"
        message = "Popped 6-mans queues **{}** members to their team voice channel.".format(action)
        await ctx.send(message)

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setCategory(self, ctx, category_channel: discord.CategoryChannel):
        """Sets the 6 mans category channel where all 6 mans channels will be created under"""
        await self._save_category(ctx, category_channel.id)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def getCategory(self, ctx):
        """Gets the channel currently assigned as the transaction channel"""
        try:
            await ctx.send("6 mans category channel set to: {0}".format((await self._category(ctx)).mention))
        except:
            await ctx.send(":x: 6 mans category channel not set")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def unsetCategory(self, ctx):
        """Unsets the 6 mans category channel. 6 mans channels will not be created if this is not set"""
        category = await self._category(ctx)
        old_helper_role = await self._helper_role(ctx)
        if old_helper_role and category:
            await category.set_permissions(old_helper_role, overwrite=None)
        await self._save_category(ctx, None)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setHelperRole(self, ctx, helper_role: discord.Role):
        """Sets the 6 mans helper role. Anyone with this role will be able to see all the game channels that are created"""
        await self._save_helper_role(ctx, helper_role.id)
        category = await self._category(ctx)
        # await category.edit(overwrites={helper_role: discord.PermissionOverwrite(read_messages=True, manage_channels=True, connect=True)})
        await category.set_permissions(helper_role, read_messages=True, manage_channels=True, connect=True)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def getHelperRole(self, ctx):
        """Gets the channel currently assigned as the transaction channel"""
        try:
            await ctx.send("6 mans helper role set to: {0}".format((await self._helper_role(ctx)).name))
        except:
            await ctx.send(":x: 6 mans helper role not set")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def unsetHelperRole(self, ctx):
        """Unsets the 6 mans helper role."""
        category = await self._category(ctx)
        old_helper_role = await self._helper_role(ctx)
        if old_helper_role and category:
            await category.set_permissions(old_helper_role, overwrite=None)
        await self._save_helper_role(ctx, None)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command(aliases=["cag"])
    async def checkActiveGames(self, ctx):
        if not await self.has_perms(ctx):
            return

        await self._pre_load_queues(ctx)
        await self._pre_load_games(ctx, False)
        queueGames = {}
        for game in self.games:
            if game.queueId in queueGames.keys():
                queueGames[game.queueId].append(game)
            else:
                queueGames[game.queueId] = [game]
        
        embed = discord.Embed(title="6Mans Active Games", color=discord.Colour.blue())

        for queue_id in queueGames.keys():
            queue_games = queueGames[queue_id]
            queue_name = next(queue.name for queue in self.queues if queue.id == queue_id)
            embed.add_field(name="{}:".format(queue_name), value="{}".format("\n".join(["{0}\n{1}".format(str(game.id), ", ".join([player.mention for player in game.players])) for game in queue_games])), inline=False)

        await ctx.channel.send(embed=embed)


    @commands.Cog.listener("on_reaction_add")
    async def process_shuffle_vote(self, reaction, user):
        message = reaction.message
        channel = reaction.message.channel
        action_emojis = [self.SHUFFLE_REACT]
        if reaction.emoji not in action_emojis or user.id == self.bot.user.id:
            return False
        # await reaction.remove(user)
        # await reaction.message.add_reaction(self.SHUFFLE_REACT)
        
        # Find Game and Queue
        game, queue = self._get_game_and_queue(channel)
        
        if message != game.teams_message:
            return False
        # Is vote enough?
        # if user not in game.voted_remake:
        #     game.voted_remake.append(user)
        guild = reaction.message.channel.guild
        
        if reaction.count > int(len(game.players)/2):
            await channel.send("{} _Generating New teams..._".format(self.SHUFFLE_REACT))
            await message.edit(embed=await self._get_updated_game_info_embed(guild, game, queue, invalid=True, prefix='?'))
            await game.shuffle_players()
            embed = await self._get_updated_game_info_embed(guild, game, queue, invalid=False, prefix='?')
            await self._display_teams(game, embed)


    async def has_perms(self, ctx):
        helper_role = await self._helper_role(ctx)
        if ctx.author.guild_permissions.administrator:
            return True
        elif helper_role and helper_role in ctx.author.roles:
            return True

    async def _add_to_queue(self, player, six_mans_queue):
        six_mans_queue._put(player)
        player_list = self._format_player_list(six_mans_queue)

        embed = discord.Embed(color=discord.Colour.green())
        embed.set_author(name="{0} added to the {1} queue. ({2}/{3})".format(player.display_name, six_mans_queue.name,
            six_mans_queue.queue.qsize(), team_size), icon_url="{}".format(player.avatar_url))
        embed.add_field(name="Players in Queue", value=player_list, inline=False)

        for channel in six_mans_queue.channels:
            await channel.send(embed=embed)

    async def _remove_from_queue(self, player, six_mans_queue):
        six_mans_queue._remove(player)
        player_list = self._format_player_list(six_mans_queue)

        embed = discord.Embed(color=discord.Colour.red())
        embed.set_author(name="{0} removed from the {1} queue. ({2}/{3})".format(player.display_name, six_mans_queue.name,
            six_mans_queue.queue.qsize(), team_size), icon_url="{}".format(player.avatar_url))
        embed.add_field(name="Players in Queue", value=player_list, inline=False)

        for channel in six_mans_queue.channels:
            await channel.send(embed=embed)

    async def _auto_remove_from_queue(self, player, six_mans_queue):
        try:
            await self._remove_from_queue(player, six_mans_queue)
            await player.send("You have been timed out from the {} 6 mans queue. You'll need to use the "
                "queue command again if you wish to play some more.".format(six_mans_queue.name))
        except:
            pass

    async def timeout_queues(self):
        """Loop task that checks if any players in a queue have been in there longer than the max queue time and need to be timed out."""
        await self.bot.wait_until_ready()
        while self.bot.get_cog("SixMans") == self:
            deadline = datetime.datetime.now() - datetime.timedelta(seconds=player_timeout_time)           
            for queue in self.queues:
                players_to_remove = []
                ids_to_remove = []
                for player_id, join_time in queue.activeJoinLog.items():
                    if join_time < deadline:
                        try:
                            player = self.bot.get_user(player_id)
                            if player:
                                players_to_remove.append(player)
                            else:
                                # Can't see the user (no shared servers)
                                ids_to_remove.append(player_id)  
                        except discord.HTTPException:
                            pass
                        except:
                            ids_to_remove.append(player_id)
                for player in players_to_remove:
                    await self._auto_remove_from_queue(player, queue)
                for player_id in ids_to_remove:
                    try:
                        del queue.activeJoinLog[player_id]
                    except:
                        pass
            await asyncio.sleep(loop_time)
            
    async def _finish_game(self, ctx, game, six_mans_queue, winning_team):
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

        if await self._get_automove(ctx): # game.automove not working?
            qlobby_vc = await self._get_q_lobby_vc(ctx)
            if qlobby_vc:
                await self._move_to_voice(qlobby_vc, game.voiceChannels[0].members)
                await self._move_to_voice(qlobby_vc, game.voiceChannels[1].members)

        await self._remove_game(ctx, game)

    async def _move_to_voice(self, vc: discord.VoiceChannel, members):
        for member in members:
            try:
                await member.move_to(vc)
            except:
                pass

    async def _remove_game(self, ctx, game):
        self.games.remove(game)
        await self._save_games(ctx, self.games)
        await asyncio.sleep(30)
        q_lobby_vc = await self._get_q_lobby_vc(ctx)
        try:
            await game.textChannel.delete()
        except:
            pass
        for vc in game.voiceChannels:
            try:
                try:
                    if q_lobby_vc:
                        for player in vc.members:
                            await player.move_to(q_lobby_vc)
                except:
                    pass
                await vc.delete()
            except:
                pass

    def _get_opposing_captain(self, ctx, game):
        opposing_captain = None
        if ctx.author in game.blue:
            opposing_captain = game.captains[1] #Orange team captain
        elif ctx.author in game.orange:
            opposing_captain = game.captains[0] #Blue team captain
        return opposing_captain

    def _swap_opposing_captain(self, game, opposing_captain):
        if opposing_captain in game.blue:
            game.captains[0] = random.sample(list(game.blue), 1)[0] #Swap Blue team captain
        elif opposing_captain in game.orange:
            game.captains[1] = random.sample(list(game.orange), 1)[0] #Swap Orange team captain

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
            "Queue": six_mans_queue.id,
            "Player": player.id,
            "Win": win,
            "Points": points_earned,
            "DateTime": date_time
        }

    def _filter_scores(self, scores, start_date, queue_id):
        players = {}
        valid_scores = 0
        for score in scores:
            date_time = datetime.datetime.strptime(score["DateTime"], "%d-%b-%Y (%H:%M:%S.%f)")
            if  date_time > start_date and (queue_id is None or score["Queue"] == queue_id):
                self._give_points(players, score)
                valid_scores +=1
            else:
                break
        return players, (valid_scores // 6)

    def _sort_player_dict(self, player_dict):
        sorted_players = sorted(player_dict.items(), key=lambda x: x[1][player_wins_key], reverse=True)
        return sorted(sorted_players, key=lambda x: x[1][player_points_key], reverse=True)

    async def _format_leaderboard(self, ctx, sorted_players, queue_name, games_played, lb_format):
        embed = discord.Embed(title="{0} 6 Mans {1} Leaderboard".format(queue_name, lb_format), color=discord.Colour.blue())
        embed.add_field(name="Games Played", value="{}\n".format(games_played), inline=True)
        embed.add_field(name="Unique Players", value="{}\n".format(len(sorted_players)), inline=True)
        
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
            if author_index is not None and author_index > 9:
                author_info = sorted_players[author_index][1]
                message += "\n\n`{0}` {1} **Points:** {2}  **Wins:** {3}  **Games Played:** {4}".format(author_index + 1, author.mention, author_info[player_points_key], 
                    author_info[player_wins_key], author_info[player_gp_key])
        except Exception:
            pass

        embed.add_field(name="Most Points", value=message, inline=False)
        return embed

    def _format_rank(self, ctx, player, sorted_players, queue_name, rnk_format):
        try:
            num_players = len(sorted_players)
            points_index = [y[0] for y in sorted_players].index("{0}".format(player.id))
            player_info = sorted_players[points_index][1]
            points, wins, games_played = player_info[player_points_key], player_info[player_wins_key], player_info[player_gp_key]
            wins_index = [y[0] for y in sorted(sorted_players, key=lambda x: x[1][player_wins_key], reverse=True)].index("{0}".format(player.id))
            games_played_index = [y[0] for y in sorted(sorted_players, key=lambda x: x[1][player_gp_key], reverse=True)].index("{0}".format(player.id))
            embed = discord.Embed(title="{0} {1} 6 Mans {2} Rank".format(player.display_name, queue_name, rnk_format), color=discord.Colour.blue())
            embed.set_thumbnail(url=player.avatar_url)
            embed.add_field(name="Points:", value="**Value:** {2} | **Rank:** {0}/{1}".format(points_index + 1, num_players, points), inline=True)
            embed.add_field(name="Wins:", value="**Value:** {2} | **Rank:** {0}/{1}".format(wins_index + 1, num_players, wins), inline=True)
            embed.add_field(name="Games Played:", value="**Value:** {2} | **Rank:** {0}/{1}".format(games_played_index + 1, num_players, games_played), inline=True)
        except:
            embed = discord.Embed(title="{0} {1} 6 Mans {2} Rank".format(player.display_name, queue_name, rnk_format), color=discord.Colour.red(),
                description="No stats yet to rank {}".format(player.mention))
            embed.set_thumbnail(url=player.avatar_url)
        return embed

    async def _select_teams(self, ctx, six_mans_queue):
        game = await self._create_game(ctx, six_mans_queue)
        if game is None:
            return False
        
        #Remove players from any other queue they were in
        for player in game.players:
            for queue in self.queues:
                if player in queue.queue:
                    await self._remove_from_queue(player, queue)

        if True: # TODO: add other methods of player selection (i.e. captains)
            await game.shuffle_players()

        # Display teams
        embed = await self._get_game_info_embed(ctx, game, six_mans_queue)
        await self._display_teams(game, embed)
        
        self.games.append(game)
        await self._save_games(ctx, self.games)
        return True

    async def _display_teams(self, game, embed):
        lobby_info_msg = await game.textChannel.send(embed=embed)
        await lobby_info_msg.add_reaction(self.SHUFFLE_REACT)
        game.teams_message = lobby_info_msg

    async def _get_game_info_embed(self, ctx, game, six_mans_queue):
        helper_role = await self._helper_role(ctx)
        await game.textChannel.send("{}\n".format(", ".join([player.mention for player in game.players])))
        embed = discord.Embed(title="{0} 6 Mans Game Info".format(six_mans_queue.name), color=discord.Colour.blue())
        embed.add_field(name="Blue Team", value="{}\n".format(", ".join([player.mention for player in game.blue])), inline=False)
        embed.add_field(name="Orange Team", value="{}\n".format(", ".join([player.mention for player in game.orange])), inline=False)
        embed.add_field(name="Captains", value="**Blue:** {0}\n**Orange:** {1}".format(game.captains[0].mention, game.captains[1].mention), inline=False)
        embed.add_field(name="Lobby Info", value="**Name:** {0}\n**Password:** {1}".format(game.roomName, game.roomPass), inline=False)
        embed.add_field(name="Point Breakdown", value="**Playing:** {0}\n**Winning Bonus:** {1}"
            .format(six_mans_queue.points[pp_play_key], six_mans_queue.points[pp_win_key]), inline=False)
        embed.add_field(name="Additional Info", value="Feel free to play whatever type of series you want, whether a bo3, bo5, or any other.\n\n"
            "When you are done playing with the current teams please report the winning team using the command `{0}sr [winning_team]` where "
            "the `winning_team` parameter is either `Blue` or `Orange`. Both teams will need to verify the results.\n\nIf you wish to cancel "
            "the game and allow players to queue again you can use the `{0}cg` command. Both teams will need to verify that they wish to "
            "cancel the game.".format(ctx.prefix), inline=False)
        help_message = "If you think the bot isn't working correctly or have suggestions to improve it, please contact adammast."
        if helper_role:
            help_message = "If you need any help or have questions please contact someone with the {0} role. ".format(helper_role.mention) + help_message
        embed.add_field(name="Help", value=help_message, inline=False)
        return embed

    # here
    async def _get_updated_game_info_embed(self, guild, game, six_mans_queue, invalid=False, prefix='?'):
        helper_role = await self._helper_role_from_guild(guild)
        sm_title = "{0} 6 Mans Game Info".format(six_mans_queue.name)
        if invalid:
            sm_title += " :x: [Teams Changed]"
        embed = discord.Embed(title=sm_title, color=discord.Colour.blue())
        embed.add_field(name="Blue Team", value="{}\n".format(", ".join([player.mention for player in game.blue])), inline=False)
        embed.add_field(name="Orange Team", value="{}\n".format(", ".join([player.mention for player in game.orange])), inline=False)
        if not invalid:
            embed.add_field(name="Captains", value="**Blue:** {0}\n**Orange:** {1}".format(game.captains[0].mention, game.captains[1].mention), inline=False)
        embed.add_field(name="Lobby Info", value="**Name:** {0}\n**Password:** {1}".format(game.roomName, game.roomPass), inline=False)
        embed.add_field(name="Point Breakdown", value="**Playing:** {0}\n**Winning Bonus:** {1}"
            .format(six_mans_queue.points[pp_play_key], six_mans_queue.points[pp_win_key]), inline=False)
        if not invalid:
            embed.add_field(name="Additional Info", value="Feel free to play whatever type of series you want, whether a bo3, bo5, or any other.\n\n"
                "When you are done playing with the current teams please report the winning team using the command `{0}sr [winning_team]` where "
                "the `winning_team` parameter is either `Blue` or `Orange`. Both teams will need to verify the results.\n\nIf you wish to cancel "
                "the game and allow players to queue again you can use the `{0}cg` command. Both teams will need to verify that they wish to "
                "cancel the game.".format(prefix), inline=False)
        help_message = "If you think the bot isn't working correctly or have suggestions to improve it, please contact adammast."
        if helper_role:
            help_message = "If you need any help or have questions please contact someone with the {0} role. ".format(helper_role.mention) + help_message
        embed.add_field(name="Help", value=help_message, inline=False)
        return embed

    async def _create_game(self, ctx, six_mans_queue):
        if not six_mans_queue._queue_full():
            return None
        players = [six_mans_queue._get() for _ in range(team_size)]
        for channel in six_mans_queue.channels:
            await channel.send("**Queue is full! Game is being created.**")
        text_channel, voice_channels = await self._create_game_channels(ctx, six_mans_queue)

        for player in players:
            await text_channel.set_permissions(player, read_messages=True)

        automove = await self._get_automove(ctx)
        game = Game(players, text_channel, voice_channels, six_mans_queue.id, automove)
        await game.append_channel_short_codes()
        return game

    async def _create_game_channels(self, ctx, six_mans_queue):
        # sync permissions on channel creation, and edit overwrites (@everyone) immediately after
        guild = ctx.message.guild
        helper_role = await self._helper_role(ctx)
        category = await self._category(ctx)
        text_channel = await guild.create_text_channel(
            "{0} 6 Mans".format(six_mans_queue.name), 
            permissions_synced=True,
            category=category
        )
        await text_channel.set_permissions(guild.default_role, view_channel=False, read_messages=False)
        
        blue_vc = await guild.create_voice_channel("{0} Blue Team".format(six_mans_queue.name), category=await self._category(ctx))
        await blue_vc.set_permissions(guild.default_role, connect=False)
        oran_vc = await guild.create_voice_channel("{0} Orange Team".format(six_mans_queue.name),  permissions_synced=True, category=await self._category(ctx))
        await oran_vc.set_permissions(guild.default_role, connect=False)
        
        # manually add helper role perms if there is not an associated 6mans category
        if helper_role and not category:
            await text_channel.set_permissions(helper_role, view_channel=True, read_messages=True)
            await blue_vc.set_permissions(helper_role, connect=True)
            await oran_vc.set_permissions(helper_role, connect=True)
        
        voice_channels = [blue_vc, oran_vc]
        return text_channel, voice_channels

    async def _get_info(self, ctx):
        game = self._get_game(ctx)
        if game is None:
            await ctx.send(":x: This command can only be used in a 6 mans game channel.")
            return None

        six_mans_queue = None
        for queue in self.queues:
            if queue.id == game.queueId:
                six_mans_queue = queue

        if six_mans_queue is None:
            await ctx.send(":x: Queue not found for this channel, please message an Admin if you think this is a mistake.")
            return None
        
        return game, six_mans_queue

    def _get_game(self, ctx):
        for game in self.games:
            if game.textChannel == ctx.channel:
                return game

    def _get_queue(self, ctx):
        for six_mans_queue in self.queues:
            for channel in six_mans_queue.channels:
                if channel == ctx.channel:
                    return six_mans_queue

    def _get_queue_name(self, ctx, queue_name):
        if queue_name is None:
            return ctx.guild.name
        else:
            for queue in self.queues:
                if queue.name.lower() == queue_name.lower():
                    return queue.name

    def _get_queue_id_by_name(self, queue_name):
        if queue_name is None:
            return None
        else:
            for queue in self.queues:
                if queue.name.lower() == queue_name.lower():
                    return queue.id

    def _format_queue_info(self, ctx, queue):
        embed = discord.Embed(title="{0} 6 Mans Info".format(queue.name), color=discord.Colour.blue())
        embed.add_field(name="Channels", value="{}\n".format(", ".join([channel.mention for channel in queue.channels])), inline=False)
        embed.add_field(name="Games Played", value="{}\n".format(queue.gamesPlayed), inline=False)
        embed.add_field(name="Unique Players All-Time", value="{}\n".format(len(queue.players)), inline=False)
        embed.add_field(name="Point Breakdown", value="**Per Series Played:** {0}\n**Per Series Win:** {1}"
            .format(queue.points[pp_play_key], queue.points[pp_win_key]), inline=False)
        return embed

    def _format_queue(self, ctx, queue):
        player_list = self._format_player_list(queue)
        embed = discord.Embed(title="{0} 6 Mans Queue".format(queue.name), color=discord.Colour.blue())
        embed.add_field(name="Players in Queue", value=player_list, inline=False)
        return embed

    def _format_player_list(self, queue):
        player_list = "{}".format(", ".join([player.mention for player in queue.queue.queue]))
        if player_list == "":
            player_list = "No players currently in the queue"
        return player_list

    async def _pre_load_queues(self, ctx):
        if self.queues is None or self.queues == []:
            queues = await self._queues(ctx)
            self.queues = []
            for key, value in queues.items():
                queue_channels = [ctx.guild.get_channel(x) for x in value["Channels"]]
                queue_name = value["Name"]
                for queue in self.queues:
                    if queue.name == queue_name:
                        await ctx.send(":x: There is already a queue set up with the name: {0}".format(queue.name))
                        return
                    for channel in queue_channels:
                        if channel in queue.channels:
                            await ctx.send(":x: {0} is already being used for queue: {1}".format(channel.mention, queue.name))
                            return

                six_mans_queue = SixMansQueue(queue_name, ctx.guild, queue_channels, value["Points"], value["Players"], value["GamesPlayed"])
                six_mans_queue.id = int(key)
                self.queues.append(six_mans_queue)

    async def _pre_load_games(self, ctx, force_load):
        if self.games is None or self.games == [] or force_load:
            games = await self._games(ctx)
            game_list = []
            for key, value in games.items():
                players = [ctx.guild.get_member(x) for x in value["Players"]]
                text_channel = ctx.guild.get_channel(value["TextChannel"])
                voice_channels = [ctx.guild.get_channel(x) for x in value["VoiceChannels"]]
                queueId = value["QueueId"]
                game = Game(players, text_channel, voice_channels, queueId)
                game.id = int(key)
                game.captains = [ctx.guild.get_member(x) for x in value["Captains"]]
                game.blue = set([ctx.guild.get_member(x) for x in value["Blue"]])
                game.orange = set([ctx.guild.get_member(x) for x in value["Orange"]])
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

    async def _queues(self, ctx):
        return await self.config.guild(ctx.guild).Queues()

    async  def _save_queues(self, ctx, queues):
        queue_dict = {}
        for queue in queues:
            if queue.guild == ctx.guild:
                queue_dict[queue.id] = queue._to_dict()
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

    async def _get_automove(self, ctx):
        return await self.config.guild(ctx.guild).AutoMove()

    async def _save_automove(self, ctx, automove: bool):
        await self.config.guild(ctx.guild).AutoMove.set(automove)

    async def _save_category(self, ctx, category):
        await self.config.guild(ctx.guild).CategoryChannel.set(category)

    async def _save_q_lobby_vc(self, ctx, vc):
        await self.config.guild(ctx.guild).QLobby.set(vc)
    
    async def _get_q_lobby_vc(self, ctx):
        lobby_voice = await self.config.guild(ctx.guild).QLobby()
        for vc in ctx.guild.voice_channels:
            if vc.id == lobby_voice:
                return vc
        return None

    async def _helper_role(self, ctx):
        return ctx.guild.get_role(await self.config.guild(ctx.guild).HelperRole())

    async def _save_helper_role(self, ctx, helper_role):
        await self.config.guild(ctx.guild).HelperRole.set(helper_role)

class Game:
    def __init__(self, players, text_channel, voice_channels, queue_id, automove=False):
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

class SixMansQueue:
    def __init__(self, name, guild, channels, points, players, gamesPlayed):
        self.id = uuid.uuid4().int
        self.name = name
        self.queue = PlayerQueue()
        self.guild = guild
        self.channels = channels
        self.points = points
        self.players = players
        self.gamesPlayed = gamesPlayed
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
        return self.queue.qsize() >= team_size

    def _to_dict(self):
        return {
            "Name": self.name,
            "Channels": [x.id for x in self.channels],
            "Points": self.points,
            "Players": self.players,
            "GamesPlayed": self.gamesPlayed
        }

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
