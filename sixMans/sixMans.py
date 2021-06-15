import asyncio
import datetime
import random
from typing import Dict, List

import discord
from discord.ext.commands import Context
from redbot.core import Config, checks, commands
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

from .game import Game
from .queue import SixMansQueue
from .strings import Strings

DEBUG = True
MINIMUM_GAME_TIME = 600                     # Seconds (10 Minutes)
PLAYER_TIMEOUT_TIME = 14400                 # How long players can be in a queue in seconds (4 Hours)
LOOP_TIME = 5                               # How often to check the queues in seconds
VERIFY_TIMEOUT = 15                         # How long someone has to react to a prompt (seconds)
CHANNEL_SLEEP_TIME = 5 if DEBUG else 30     # How long channels will persist after a game's score has been reported (seconds)

QTS_METHODS = [
    Strings.VOTE_TS,
    Strings.CAPTAINS_TS,
    Strings.RANDOM_TS,
    Strings.BALANCED_TS,
]  # , Strings.SHUFFLE_TS, Strings.BALANCED_TS]
defaults = {
    "CategoryChannel": None,
    "HelperRole": None,
    "AutoMove": False,
    "QLobby": None,
    "DefaultTeamSelection": Strings.RANDOM_TS,
    "Games": {},
    "Queues": {},
    "GamesPlayed": 0,
    "Players": {},
    "Scores": []
}

class SixMans(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567896, force_registration=True)
        self.config.register_guild(**defaults)
        self.queueMaxSize = 6
        self.queues: list[SixMansQueue] = []
        self.games: list[Game] = []
        self.task = self.bot.loop.create_task(self.timeout_queues())
        self.observers = set()

    def cog_unload(self):
        """Clean up when cog shuts down."""
        if self.task:
            self.task.cancel()

#region commmands

    # region admin commands
    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def loadGames(self, ctx: Context):
        await self._pre_load_queues(ctx.guild)
        msg = await ctx.send("{0} Please verify that you wish to reload the games.".format(ctx.author.mention))
        start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)

        pred = ReactionPredicate.yes_or_no(msg, ctx.author)
        await ctx.bot.wait_for("reaction_add", check=pred)
        if pred.result is True:
            await self._pre_load_games(ctx.guild)
            await ctx.send("Done")
        else:
            await ctx.send(":x: Games **not** reloaded.")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearSixMansData(self, ctx: Context):
        msg = await ctx.send("{0} Please verify that you wish to clear **all** of the {1} Mans data.".format(ctx.author.mention, self.queueMaxSize))
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
    async def addNewQueue(self, ctx: Context, name, points_per_play: int, points_per_win: int, *channels):
        await self._pre_load_queues(ctx.guild)
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

        points = {Strings.PP_PLAY_KEY: points_per_play, Strings.PP_WIN_KEY: points_per_win}
        team_selection = await self._team_selection(ctx.guild)
        six_mans_queue = SixMansQueue(name, ctx.guild, queue_channels, points, {}, 0, self.queueMaxSize, team_selection)
        self.queues.append(six_mans_queue)
        await self._save_queues(ctx.guild, self.queues)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def editQueue(self, ctx: Context, current_name, new_name, points_per_play: int, points_per_win: int, *channels):
        await self._pre_load_queues(ctx.guild)
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
        six_mans_queue.points = {Strings.PP_PLAY_KEY: points_per_play, Strings.PP_WIN_KEY: points_per_win}
        six_mans_queue.channels = queue_channels
        await self._save_queues(ctx.guild, self.queues)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command(aliases=['setQTS', 'setQueueTeamSelection', 'sqts'])
    @checks.admin_or_permissions(manage_guild=True)
    async def setQueueTS(self, ctx: Context, queue_name, team_selection):
        """Sets the team selection mode for a specific queue"""
        await self._pre_load_queues(ctx.guild)
        six_mans_queue = None
        for queue in self.queues:
            if queue.name == queue_name:
                six_mans_queue = queue
                break

        if six_mans_queue is None:
            await ctx.send(":x: No queue found with name: {0}".format(current_name))
            return
        
        valid_ts = self.is_valid_ts(team_selection)

        if valid_ts:
            await six_mans_queue.set_team_selection(valid_ts)
            await self._save_queues(ctx.guild, self.queues)
            await ctx.send("Done")
        else:
            await ctx.send(":x: **{}** is not a valid team selection method.".format(team_selection))

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def removeQueue(self, ctx: Context, *, queue_name):
        await self._pre_load_queues(ctx.guild)
        for queue in self.queues:
            if queue.name == queue_name:
                self.queues.remove(queue)
                await self._save_queues(ctx.guild, self.queues)
                await ctx.send("Done")
                return
        await ctx.send(":x: No queue set up with name: {0}".format(queue_name))

    @commands.guild_only()
    @commands.command(aliases=["qm", "queueAll", "qa", "forceQueue", "fq"])
    @checks.admin_or_permissions(manage_guild=True)
    async def queueMultiple(self, ctx: Context, *members: discord.Member):
        """Mass queueing for testing purposes"""
        await self._pre_load_queues(ctx.guild)
        await self._pre_load_games(ctx.guild)
        six_mans_queue = self._get_queue_by_text_channel(ctx.channel)
        for member in members:
            if member in six_mans_queue.queue.queue:
                await ctx.send("{} is already in queue.".format(member.display_name))
                break
            await self._add_to_queue(member, six_mans_queue)
        if six_mans_queue._queue_full():
            await self._pop_queue(ctx, six_mans_queue)

    @commands.guild_only()
    @commands.command(aliases=["kq"])
    async def kickQueue(self, ctx: Context, player: discord.Member):
        """Remove someone else from the queue"""
        if not await self.has_perms(ctx.author):
            return

        await self._pre_load_queues(ctx.guild)
        six_mans_queue = self._get_queue_by_text_channel(ctx.channel)
        if player in six_mans_queue.queue:
            await self._remove_from_queue(player, six_mans_queue)
        else:
            await ctx.send("{} is not in queue.".format(player.display_name))

    @commands.guild_only()
    @commands.command(aliases=["fcg"])
    async def forceCancelGame(self, ctx: Context, gameId: int = None):
        """Cancel the current game. Can only be used in a game channel unless a gameId is given.
        The game will end with no points given to any of the players. The players with then be allowed to queue again."""
        if not await self.has_perms(ctx.author):
            return
        
        await self._pre_load_queues(ctx.guild)
        await self._pre_load_games(ctx.guild)
        game = None
        if gameId is None:
            game = self._get_game_by_text_channel(ctx.channel)
            if game is None:
                await ctx.send(":x: This command can only be used in a {} Mans game channel.".format(self.queueMaxSize))
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
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=VERIFY_TIMEOUT)
            if pred.result is True:
                await ctx.send("Done.")
                try:
                    # If the text channel has been deleted this will throw an error and we'll instead want to send the message to wherever the command was used
                    await game.textChannel.send("Game canceled by {}. Feel free to queue again in an appropriate channel.\n**This game's channels will be deleted in {} seconds**".format(ctx.author.mention, CHANNEL_SLEEP_TIME))
                except:
                    await ctx.send("Game canceled by {}. Feel free to queue again in an appropriate channel.\n**This game's channels will be deleted in {} seconds**".format(ctx.author.mention, CHANNEL_SLEEP_TIME))
                await self._remove_game(ctx.guild, game)
            else:
                await ctx.send(":x: Cancel not verified. To cancel the game you will need to use the `{0}cg` command again.".format(ctx.prefix))
        except asyncio.TimeoutError:
            await ctx.send(":x: Cancel not verified in time. To cancel the game you will need to use the `{0}cg` command again.".format(ctx.prefix))   

    @commands.guild_only()
    @commands.command(aliases=["fr"])
    async def forceResult(self, ctx: Context, winning_team):
        if not await self.has_perms(ctx.author):
            return

        await self._pre_load_queues(ctx.guild)
        await self._pre_load_games(ctx.guild)
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

        await game.report_winner(winning_team)
        await ctx.send("Done. Thanks for playing!\n**This channel and the team voice channels will be deleted in {} seconds**".format(CHANNEL_SLEEP_TIME))
        await self._finish_game(ctx.guild, game, six_mans_queue, winning_team)

    #endregion

    #region player commands
    @commands.guild_only()
    @commands.command(aliases=["smMove", "moveme"])
    async def moveMe(self, ctx: Context):
        await self._pre_load_queues(ctx.guild)
        await self._pre_load_games(ctx.guild)
        if ctx.message.channel.category != await self._category(ctx.guild):
            return False

        game = self._get_game_by_text_channel(ctx.channel)
        player = ctx.message.author
        if game:
            try:
                if player in game.blue:
                    await player.move_to(game.voiceChannels[0])
                if player in game.orange:
                    await player.move_to(game.voiceChannels[1])
                await ctx.message.add_reaction(Strings.WHITE_CHECK_REACT) # white_check_mark
            except:
                await ctx.message.add_reaction(Strings.WHITE_X_REACT) # negative_squared_cross_mark
                if not player.voice:
                    await ctx.send("{}, you must be connected to a voice channel to be moved to your Six Man's team channel.".format(player.mention))
        else:
            await ctx.message.add_reaction(Strings.WHITE_X_REACT) # negative_squared_cross_mark
            await ctx.send("{}, you must run this command from within your queue lobby channel.".format(player.mention))
            # TODO: determine a workaround from filtering through all active games

    @commands.guild_only()
    @commands.command(aliases=["li", "gameInfo", "gi"])
    async def lobbyInfo(self, ctx: Context):
        """Gets lobby info for the series that you are involved in"""
        # TODO: fails after cog is reloaded
        await self._pre_load_queues(ctx.guild)
        await self._pre_load_games(ctx.guild)
        if ctx.message.channel.category != await self._category(ctx.guild):
            return False

        game = self._get_game_by_text_channel(ctx.channel)
        player = ctx.message.author
        if game:
            # try:
            embed = discord.Embed(
                title="{0} {1} Mans Game Info".format(game.queue.name, game.queue.queueMaxSize),
                color=discord.Colour.green()
            )
            embed.set_thumbnail(url=ctx.guild.icon_url)
            print(game.blue)
            print(game.orange)
            embed.add_field(name="Blue", value="{}\n".format("\n".join([player.mention for player in game.blue])), inline=True)
            embed.add_field(name="Orange", value="{}\n".format("\n".join([player.mention for player in game.orange])), inline=True)

            embed.add_field(name="Lobby Info", value="```{} // {}```".format(game.roomName, game.roomPass), inline=False)
            embed.set_footer(text="Game ID: {}".format(game.id))
            await ctx.send(embed=embed)
            await ctx.send(':)')
            await ctx.message.add_reaction(Strings.WHITE_CHECK_REACT) # white_check_mark
            # except:
            #     await ctx.message.add_reaction(Strings.WHITE_X_REACT) # negative_squared_cross_mark
        else:
            await ctx.message.add_reaction(Strings.WHITE_X_REACT) # negative_squared_cross_mark
            await ctx.send("{}, you must run this command from within your queue lobby channel.".format(player.mention))
            # TODO: determine a workaround from filtering through all active games
    
    @commands.guild_only()
    @commands.command(aliases=["q"])
    async def queue(self, ctx: Context):
        """Add yourself to the queue"""
        await self._pre_load_queues(ctx.guild)
        await self._pre_load_games(ctx.guild)
        six_mans_queue = self._get_queue_by_text_channel(ctx.channel)
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
            await self._pop_queue(ctx, six_mans_queue)

    @commands.guild_only()
    @commands.command(aliases=["dq", "lq", "leaveq", "leaveQ", "unqueue", "unq", "uq"])
    async def dequeue(self, ctx: Context):
        """Remove yourself from the queue"""
        await self._pre_load_queues(ctx.guild)
        six_mans_queue = self._get_queue_by_text_channel(ctx.channel)
        player = ctx.message.author

        if player in six_mans_queue.queue:
            await self._remove_from_queue(player, six_mans_queue)
        else:
            await ctx.send(":x: You're not in the {0} queue".format(six_mans_queue.name))

    @commands.guild_only()
    @commands.command(aliases=["cg"])
    async def cancelGame(self, ctx: Context):
        """Cancel the current game. Can only be used in a game channel.
        The game will end with no points given to any of the players. The players with then be allowed to queue again."""
        await self._pre_load_queues(ctx.guild)
        await self._pre_load_games(ctx.guild)
        game = self._get_game_by_text_channel(ctx.channel)
        if game is None:
            await ctx.send(":x: This command can only be used in a {} Mans game channel.".format(self.queueMaxSize))
            return

        opposing_captain = self._get_opposing_captain(ctx.author, game)
        if opposing_captain is None:
            await ctx.send(":x: Only players on one of the two teams can cancel the game.")
            return

        msg = await ctx.send("{0} Please verify that both teams want to cancel the game. You have {1} seconds to verify".format(opposing_captain.mention, VERIFY_TIMEOUT))
        start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)

        pred = ReactionPredicate.yes_or_no(msg, opposing_captain)
        try:
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=VERIFY_TIMEOUT)
            if pred.result is True:
                await ctx.send("Done. Feel free to queue again in an appropriate channel.\n**This channel will be deleted in {} seconds**".format(CHANNEL_SLEEP_TIME))
                await self._remove_game(ctx.guild, game)
            else:
                await ctx.send(":x: Cancel not verified. To cancel the game you will need to use the `{0}cg` command again.".format(ctx.prefix))
        except asyncio.TimeoutError:
            self._swap_opposing_captain(game, opposing_captain)
            await ctx.send(":x: Cancel not verified in time. To cancel the game you will need to use the `{0}cg` command again."
                "\n**If one of the captains is afk, have someone from that team use the command.**".format(ctx.prefix))

    @commands.guild_only()
    @commands.command(aliases=["sr"])
    async def scoreReport(self, ctx: Context, winning_team):
        """Report which team won the series. Can only be used in a game channel.
        Only valid after 10 minutes have passed since the game started. Both teams will need to verify the results.

        `winning_team` must be either `Blue` or `Orange`"""
        await self._pre_load_queues(ctx.guild)
        await self._pre_load_games(ctx.guild)
        game_time = ctx.message.created_at - ctx.channel.created_at
        if game_time.seconds < MINIMUM_GAME_TIME:
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

        opposing_captain = self._get_opposing_captain(ctx.author, game)
        if opposing_captain is None:
            await ctx.send(":x: Only players on one of the two teams can report the score")
            return

        msg = await ctx.send("{0} Please verify that the **{1}** team won the series. You have {2} seconds to verify"
            .format(opposing_captain.mention, winning_team, VERIFY_TIMEOUT))
        start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)

        game.scoreReported = True
        pred = ReactionPredicate.yes_or_no(msg, opposing_captain)
        try:
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=VERIFY_TIMEOUT)
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

        await game.report_winner(winning_team)
        await ctx.send("Done. Thanks for playing!\n**This channel and the team voice channels will be deleted in {} seconds**".format(CHANNEL_SLEEP_TIME))
        await self._finish_game(ctx.guild, game, six_mans_queue, winning_team)

    #regionend player commands

    #region listeners

    @commands.guild_only()
    @commands.Cog.listener("on_reaction_add")
    async def process_six_mans_reaction(self, reaction, user):
        if user.bot:
            return
        # await self._pre_load_games(user.guild)
        message = reaction.message
        channel = reaction.message.channel
        
        # Find Game and Queue
        game, queue = self._get_game_and_queue(channel)
        
        if not game:
            return False
        if message != game.info_message:
            return False

        # team_selection_mode = await self._team_selection(user.guild)
        team_selection_mode = game.teamSelection.lower()

        if team_selection_mode == Strings.VOTE_TS.lower():
            await game.process_team_select_vote(reaction, user)

        elif team_selection_mode == Strings.CAPTAINS_TS.lower():
            teams_complete = await game.process_captains_pick(reaction, user)

        elif team_selection_mode == Strings.SHUFFLE_TS.lower():
            if reaction.emoji is not Strings.SHUFFLE_REACT:
                return

            guild = reaction.message.channel.guild
            
            # Check if Shuffle is enabled
            message = self.info_message
            now = datetime.datetime.utcnow()
            time_since_last_team = (now - message.created_at).seconds
            time_since_q_pop = (now - message.channel.created_at).seconds
            if time_since_q_pop > 300:
                await reaction.clear()
                return await reaction.message.channel.send(":x: Reshuffling teams is no longer permitted after 5 minutes of the initial team selection.")
            if time_since_last_team > 180:
                await reaction.clear()
                return await reaction.message.channel.send(":x: Reshuffling teams is only permitted for 3 minutes since the previous team selection.")

            shuffle_players = reaction.count >= int(len(game.players)/2)+1
            if shuffle_players:
                await channel.send("{} _Generating New teams..._".format(Strings.SHUFFLE_REACT))
                await game.shuffle_players()

    @commands.Cog.listener("on_reaction_remove")
    async def process_six_mans_vote_rm(self, reaction, user):
        if user.bot:
            return
        # await self._pre_load_games(user.guild)
        # Un-vote if reaction pertains to a Six Mans TS Vote
        try:
            game, queue = self._get_game_and_queue(reaction.message.channel)
            if game.teamSelection.lower() == Strings.VOTE_TS.lower():
                await game.process_team_select_vote(reaction, user, added=False)
        except:
            pass

    @commands.guild_only()
    @commands.Cog.listener("on_guild_channel_delete")
    async def on_guild_channel_delete(self, channel):
        """If a queue channel is deleted, removes it from the queue class instance. If the last queue channel is deleted, the channel is replaced."""
        #TODO: Error catch if Q Lobby VC is deleted
        if type(channel) != discord.TextChannel:
            return
        await self._pre_load_queues(channel.guild)
        queue = None
        for queue in self.queues:
            if channel in queue.channels:
                queue.channels.remove(channel)
                break
        if queue.channels:
            return
        
        clone = await channel.clone()
        helper_role = await self._helper_role(channel.guild)
        helper_ping = " {}".format(helper_role.mention) if helper_role else ""
        await clone.send(":grey_exclamation:{0} This channel has been created because the last textChannel for the **{1}** queue has been deleted.".format(helper_ping, queue.name))
        queue.channels.append(clone)
        await self._save_queues(channel.guild, self.queues)

    #endregion

    #region leaderboard commands

    @commands.guild_only()
    @commands.group(aliases=["qlb"])
    async def queueLeaderBoard(self, ctx: Context):
        """Get the top ten players in points for the specific queue. If no queue name is given the list will be the top ten players across all queues.
        If you're not in the top ten your name and rank will be shown at the bottom of the list."""

    @commands.guild_only()
    @queueLeaderBoard.command(aliases=["all-time", "alltime"])
    async def overall(self, ctx: Context, *, queue_name: str = None):
        """All-time leader board"""
        await self._pre_load_queues(ctx.guild)
        players = None
        if queue_name is not None:
            for queue in self.queues:
                if queue.name.lower() == queue_name.lower():
                    queue_name = queue.name
                    players = queue.players
                    games_played = queue.gamesPlayed
        else:
            players = await self._players(ctx.guild)
            queue_name = ctx.guild.name
            games_played = await self._games_played(ctx.guild)

        if players is None or players == {}:
            await ctx.send(":x: Queue leaderboard not available for {0}".format(queue_name))
            return

        sorted_players = self._sort_player_dict(players)
        await ctx.send(embed=await self.embed_leaderboard(ctx, sorted_players, queue_name, games_played, "All-time"))

    @commands.guild_only()
    @queueLeaderBoard.command(aliases=["daily"])
    async def day(self, ctx: Context, *, queue_name: str = None):
        """Daily leader board. All games from the last 24 hours will count"""
        await self._pre_load_queues(ctx.guild)
        scores = await self._scores(ctx.guild)

        queue_id = self._get_queue_id_by_name(queue_name)
        day_ago = datetime.datetime.now() - datetime.timedelta(days=1)
        players, games_played = self._filter_scores(scores, day_ago, queue_id)

        if players is None or players == {}:
            await ctx.send(":x: Queue leaderboard not available for {0}".format(queue_name))
            return

        queue_name = self._get_queue_name(ctx.guild, queue_name)
        sorted_players = self._sort_player_dict(players)
        await ctx.send(embed=await self.embed_leaderboard(ctx, sorted_players, queue_name, games_played, "Daily"))

    @commands.guild_only()
    @queueLeaderBoard.command(aliases=["weekly", "wk"])
    async def week(self, ctx: Context, *, queue_name: str = None):
        """Weekly leader board. All games from the last week will count"""
        await self._pre_load_queues(ctx.guild)
        scores = await self._scores(ctx.guild)

        queue_id = self._get_queue_id_by_name(queue_name)
        week_ago = datetime.datetime.now() - datetime.timedelta(weeks=1)
        players, games_played = self._filter_scores(scores, week_ago, queue_id)

        if players is None or players == {}:
            await ctx.send(":x: Queue leaderboard not available for {0}".format(queue_name))
            return

        queue_name = self._get_queue_name(ctx.guild, queue_name)
        sorted_players = self._sort_player_dict(players)
        await ctx.send(embed=await self.embed_leaderboard(ctx, sorted_players, queue_name, games_played, "Weekly"))

    @commands.guild_only()
    @queueLeaderBoard.command(aliases=["monthly", "mnth"])
    async def month(self, ctx: Context, *, queue_name: str = None):
        """Monthly leader board. All games from the last 30 days will count"""
        await self._pre_load_queues(ctx.guild)
        scores = await self._scores(ctx.guild)

        queue_id = self._get_queue_id_by_name(queue_name)
        month_ago = datetime.datetime.now() - datetime.timedelta(days=30)
        players, games_played = self._filter_scores(scores, month_ago, queue_id)

        if players is None or players == {}:
            await ctx.send(":x: Queue leaderboard not available for {0}".format(queue_name))
            return

        queue_name = self._get_queue_name(ctx.guild, queue_name)
        sorted_players = self._sort_player_dict(players)
        await ctx.send(embed=await self.embed_leaderboard(ctx, sorted_players, queue_name, games_played, "Monthly"))

    #endregion

    #region rank commands

    @commands.guild_only()
    @commands.group(aliases=["rnk"])
    async def rank(self, ctx: Context):
        """Get your rank in points, wins, and games played for the specific queue. If no queue name is given it will show your overall rank across all queues."""

    @commands.guild_only()
    @rank.command(aliases=["all-time", "overall"])
    async def alltime(self, ctx: Context, player: discord.Member = None, *, queue_name: str = None):
        """All-time ranks"""
        await self._pre_load_queues(ctx.guild)
        players = None
        if queue_name is not None:
            for queue in self.queues:
                if queue.name.lower() == queue_name.lower():
                    queue_name = queue.name
                    players = queue.players
        else:
            players = await self._players(ctx.guild)
            queue_name = ctx.guild.name

        if players is None or players == {}:
            await ctx.send(":x: Player ranks not available for {0}".format(queue_name))
            return

        sorted_players = self._sort_player_dict(players)
        player = player if player else ctx.author
        await ctx.send(embed=self.embed_rank(player, sorted_players, queue_name, "All-time"))

    @commands.guild_only()
    @rank.command(aliases=["day"])
    async def daily(self, ctx: Context, player: discord.Member = None, *, queue_name: str = None):
        """Daily ranks. All games from the last 24 hours will count"""
        await self._pre_load_queues(ctx.guild)
        scores = await self._scores(ctx.guild)

        queue_id = self._get_queue_id_by_name(queue_name)
        day_ago = datetime.datetime.now() - datetime.timedelta(days=1)
        players = self._filter_scores(scores, day_ago, queue_id)[0]

        if players is None or players == {}:
            await ctx.send(":x: Player ranks not available for {0}".format(queue_name))
            return

        queue_name = self._get_queue_name(ctx.guild, queue_name)
        sorted_players = self._sort_player_dict(players)
        player = player if player else ctx.author
        await ctx.send(embed=self.embed_rank(player, sorted_players, queue_name, "Daily"))

    @commands.guild_only()
    @rank.command(aliases=["week", "wk"])
    async def weekly(self, ctx: Context, player: discord.Member = None, *, queue_name: str = None):
        """Weekly ranks. All games from the last week will count"""
        await self._pre_load_queues(ctx.guild)
        scores = await self._scores(ctx.guild)

        queue_id = self._get_queue_id_by_name(queue_name)
        week_ago = datetime.datetime.now() - datetime.timedelta(weeks=1)
        players = self._filter_scores(scores, week_ago, queue_id)[0]

        if players is None or players == {}:
            await ctx.send(":x: Player ranks not available for {0}".format(queue_name))
            return

        queue_name = self._get_queue_name(ctx.guild, queue_name)
        sorted_players = self._sort_player_dict(players)
        player = player if player else ctx.author
        await ctx.send(embed=self.embed_rank(player, sorted_players, queue_name, "Weekly"))

    @commands.guild_only()
    @rank.command(aliases=["month", "mnth"])
    async def monthly(self, ctx: Context, player: discord.Member = None, *, queue_name: str = None):
        """Monthly ranks. All games from the last 30 days will count"""
        await self._pre_load_queues(ctx.guild)
        scores = await self._scores(ctx.guild)

        queue_id = self._get_queue_id_by_name(queue_name)
        month_ago = datetime.datetime.now() - datetime.timedelta(days=30)
        players = self._filter_scores(scores, month_ago, queue_id)[0]

        if players is None or players == {}:
            await ctx.send(":x: Player ranks not available for {0}".format(queue_name))
            return

        queue_name = self._get_queue_name(ctx.guild, queue_name)
        sorted_players = self._sort_player_dict(players)
        player = player if player else ctx.author
        await ctx.send(embed=self.embed_rank(player, sorted_players, queue_name, "Monthly"))

    #endregion

#region get and set commands

    @commands.guild_only()
    @commands.command(aliases=["cq", "status"])
    async def checkQueue(self, ctx: Context):
        await self._pre_load_queues(ctx.guild)
        six_mans_queue = self._get_queue_by_text_channel(ctx.channel)
        if six_mans_queue is None:
            await ctx.send(":x: No queue set up in this channel")
            return
        await ctx.send(embed=self.embed_queue_players(six_mans_queue))

    @commands.guild_only()
    @commands.command(aliases=["setQLobby"])
    @checks.admin_or_permissions(manage_guild=True)
    async def setQueueLobby(self, ctx: Context, lobby_voice: discord.VoiceChannel):
        #TODO: Consider having the queues save the Queue Lobby VC
        await self._save_q_lobby_vc(ctx.guild, lobby_voice.id)
        await ctx.send("Done")
    
    @commands.guild_only()
    @commands.command(aliases=["unsetQueueLobby, unsetQLobby", "clearQLobby"])
    @checks.admin_or_permissions(manage_guild=True)
    async def clearQueueLobby(self, ctx: Context):
        await self._save_q_lobby_vc(ctx.guild, None)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command(aliases=["qn"])
    async def getQueueNames(self, ctx: Context):
        await self._pre_load_queues(ctx.guild)
        queue_names = ""
        for queue in self.queues:
            if queue.guild == ctx.guild:
                queue_names += "{0}\n".format(queue.name)
        await ctx.send("```Queues set up in server:\n{0}```".format(queue_names))

    @commands.guild_only()
    @commands.command(aliases=["qi"])
    async def getQueueInfo(self, ctx: Context, *, queue_name=None):
        await self._pre_load_queues(ctx.guild)
        if queue_name is not None:
            for queue in self.queues:
                if queue.name.lower() == queue_name.lower():
                    await ctx.send(embed=self.embed_queue_info(queue))
                    return
            await ctx.send(":x: No queue set up with name: {0}".format(queue_name))
            return

        six_mans_queue = self._get_queue_by_text_channel(ctx.channel)
        if six_mans_queue is None:
            await ctx.send(":x: No queue set up in this channel")
            return
        
        await ctx.send(embed=self.embed_queue_info(six_mans_queue))

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def toggleAutoMove(self, ctx: Context):
        """Toggle whether or not bot moves members to their assigned team voice channel"""
        new_automove_status = not await self._get_automove(ctx.guild)
        await self._save_automove(ctx.guild, new_automove_status)

        action = "will move" if new_automove_status else "will not move"
        message = "Popped {0} Mans queues **{1}** members to their team voice channel.".format(self.queueMaxSize, action)
        await ctx.send(message)
    
    @commands.guild_only()
    @commands.command(aliases=['setTeamSelection'])
    @checks.admin_or_permissions(manage_guild=True)
    async def setDefaultTeamSelection(self, ctx: Context, team_selection_method):
        """Set method for Six Mans team selection (Default: Random)
        
        Valid team selecion methods options:
        - **random**: selects random teams
        - **captains**: selects a captain for each team
        - **vote**: players vote for team selection method after queue pops
        - ~~**balanced**: creates balanced teams from all participating players~~
        - ~~**shuffle**: selects random teams, but allows re-shuffling teams after they have been set~~
        """
        # TODO: Support Captains [captains random, captains shuffle], Balanced
        team_selection_method = team_selection_method.lower()
        if team_selection_method not in QTS_METHODS:
            return await ctx.send("**{}** is not a valid method of team selection.".format(team_selection_method))

        if team_selection_method in ['vote', 'balanced']:
            return await ctx.send("**{}** is not currently supported as a method of team selection.".format(team_selection_method))
        
        await self._save_team_selection(ctx.guild, team_selection_method)

        await ctx.send("Done.")

    @commands.guild_only()
    @commands.command(aliases=['getTeamSelection'])
    @checks.admin_or_permissions(manage_guild=True)
    async def getDefaultTeamSelection(self, ctx: Context):
        """Get method for Six Mans team selection (Default: Random)"""
        team_selection = await self._team_selection(ctx.guild)
        await ctx.send("Six Mans team selection is currently set to **{}**.".format(team_selection))

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setCategory(self, ctx: Context, category_channel: discord.CategoryChannel):
        """Sets the category channel where all game channels will be created under"""
        await self._save_category(ctx.guild, category_channel.id)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def getCategory(self, ctx: Context):
        """Gets the channel currently assigned as the transaction channel"""
        try:
            await ctx.send("{0} Mans category channel set to: {1}".format(self.queueMaxSize, (await self._category(ctx.guild)).mention))
        except:
            await ctx.send(":x: {0} Mans category channel not set".format(self.queueMaxSize))

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def unsetCategory(self, ctx: Context):
        """Unsets the category channel. Game channels will not be created if this is not set"""
        category = await self._category(ctx.guild)
        old_helper_role = await self._helper_role(ctx.guild)
        if old_helper_role and category:
            await category.set_permissions(old_helper_role, overwrite=None)
        await self._save_category(ctx.guild, None)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setHelperRole(self, ctx: Context, helper_role: discord.Role):
        """Sets the 6 Mans helper role. Anyone with this role will be able to see all the game channels that are created"""
        await self._save_helper_role(ctx.guild, helper_role.id)
        category: discord.CategoryChannel = await self._category(ctx.guild)
        await category.set_permissions(helper_role, read_messages=True, manage_channels=True, connect=True)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def getHelperRole(self, ctx: Context):
        """Gets the role currently assigned as the 6 Mans helper role"""
        try:
            await ctx.send("{0} Mans helper role set to: {1}".format(self.queueMaxSize, (await self._helper_role(ctx.guild)).name))
        except:
            await ctx.send(":x: {0} mans helper role not set".format(self.queueMaxSize))

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def unsetHelperRole(self, ctx: Context):
        """Unsets the 6 Mans helper role."""
        category: discord.CategoryChannel = await self._category(ctx.guild)
        old_helper_role = await self._helper_role(ctx.guild)
        if old_helper_role and category:
            await category.set_permissions(old_helper_role, overwrite=None)
        await self._save_helper_role(ctx.guild, None)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command(aliases=["cag"])
    async def checkActiveGames(self, ctx: Context):
        if not await self.has_perms(ctx.author):
            return

        await self._pre_load_queues(ctx.guild)
        await self._pre_load_games(ctx.guild)
        queueGames: dict[int, list[Game]] = {}
        for game in self.games:
            queueGames.setdefault(game.queue.id, []).append(game)

        embed = self.embed_active_games(queueGames)
        await ctx.channel.send(embed=embed)

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def observers(self, ctx: Context):
        await ctx.send("There are {} observers.".format(len(self.observers)))

    #endregion

#endregion

#region helper methods

    async def has_perms(self, member: discord.Member):
        helper_role = await self._helper_role(member.guild)
        if member.guild_permissions.administrator:
            return True
        elif helper_role and helper_role in member.roles:
            return True

    async def _add_to_queue(self, player: discord.Member, six_mans_queue: SixMansQueue):
        six_mans_queue._put(player)
        embed = self.embed_player_added(player, six_mans_queue)
        await six_mans_queue.send_message(embed=embed)

    async def _remove_from_queue(self, player: discord.Member, six_mans_queue: SixMansQueue):
        six_mans_queue._remove(player)
        embed = self.embed_player_removed(player, six_mans_queue)
        await six_mans_queue.send_message(embed=embed)

    async def _auto_remove_from_queue(self, player: discord.Member, six_mans_queue: SixMansQueue):
        try:
            await self._remove_from_queue(player, six_mans_queue)
            await player.send("You have been timed out from the {0} {1} Mans queue. You'll need to use the "
                "queue command again if you wish to play some more.".format(six_mans_queue.name), self.queueMaxSize)
        except:
            pass

    async def timeout_queues(self):
        """Loop task that checks if any players in a queue have been in there longer than the max queue time and need to be timed out."""
        await self.bot.wait_until_ready()
        while self.bot.get_cog("SixMans") == self:
            deadline = datetime.datetime.now() - datetime.timedelta(seconds=PLAYER_TIMEOUT_TIME)           
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
            await asyncio.sleep(LOOP_TIME)
            
    async def _finish_game(self, guild: discord.Guild, game: Game, six_mans_queue: SixMansQueue, winning_team):
        winning_players = []
        losing_players = []
        if winning_team.lower() == "blue":
            winning_players = game.blue
            losing_players = game.orange
        else:
            winning_players = game.orange
            losing_players = game.blue

        _scores = await self._scores(guild)
        _players = await self._players(guild)
        _games_played = await self._games_played(guild)
        date_time = datetime.datetime.now().strftime("%d-%b-%Y (%H:%M:%S.%f)")
        for player in winning_players:
            score = self._create_player_score(six_mans_queue, game, player, 1, date_time)
            self._give_points(six_mans_queue.players, score)
            self._give_points(_players, score)
            _scores.insert(0, score)
        for player in losing_players:
            score = self._create_player_score(six_mans_queue, game, player, 0, date_time)
            self._give_points(six_mans_queue.players, score)
            self._give_points(_players, score)
            _scores.insert(0, score)

        _games_played += 1
        six_mans_queue.gamesPlayed += 1

        await self._save_scores(guild, _scores)
        await self._save_queues(guild, self.queues)
        await self._save_players(guild, _players)
        await self._save_games_played(guild, _games_played)

        if await self._get_automove(guild): # game.automove not working?
            qlobby_vc = await self._get_q_lobby_vc(guild)
            if qlobby_vc:
                await self._move_to_voice(qlobby_vc, game.voiceChannels[0].members)
                await self._move_to_voice(qlobby_vc, game.voiceChannels[1].members)

        await self._remove_game(guild, game)

    async def _move_to_voice(self, vc: discord.VoiceChannel, members: List[discord.Member]):
        for member in members:
            try:
                await member.move_to(vc)
            except:
                pass

    async def _remove_game(self, guild: discord.Guild, game: Game):
        self.games.remove(game)
        await self._save_games(guild, self.games)
        await asyncio.sleep(CHANNEL_SLEEP_TIME)
        q_lobby_vc = await self._get_q_lobby_vc(guild)
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

    def _get_opposing_captain(self, player: discord.Member, game: Game):
        opposing_captain = None
        if player in game.blue:
            opposing_captain = game.captains[1] #Orange team captain
        elif player in game.orange:
            opposing_captain = game.captains[0] #Blue team captain
        return opposing_captain

    def _swap_opposing_captain(self, game: Game, opposing_captain):
        if opposing_captain in game.blue:
            game.captains[0] = random.sample(list(game.blue), 1)[0] #Swap Blue team captain
        elif opposing_captain in game.orange:
            game.captains[1] = random.sample(list(game.orange), 1)[0] #Swap Orange team captain

    def _give_points(self, players_dict, score):
        player_id = score["Player"]
        points_earned = score["Points"]
        win = score["Win"]

        player_dict = players_dict.setdefault("{0}".format(player_id), {})
        player_dict[Strings.PLAYER_POINTS_KEY] = player_dict.get(Strings.PLAYER_POINTS_KEY, 0) + points_earned
        player_dict[Strings.PLAYER_GP_KEY] = player_dict.get(Strings.PLAYER_GP_KEY, 0) + 1
        player_dict[Strings.PLAYER_WINS_KEY] = player_dict.get(Strings.PLAYER_WINS_KEY, 0) + win

    def _create_player_score(self, six_mans_queue: SixMansQueue, game: Game, player: discord.Member, win, date_time):
        points_dict = six_mans_queue.points
        if win:
            points_earned = points_dict[Strings.PP_PLAY_KEY] + points_dict[Strings.PP_WIN_KEY]
        else:
            points_earned = points_dict[Strings.PP_PLAY_KEY]
        return {
            "Game": game.id,
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
        games_played = (valid_scores // self.queueMaxSize)
        return players, games_played

    def _sort_player_dict(self, player_dict):
        sorted_players = sorted(player_dict.items(), key=lambda x: x[1][Strings.PLAYER_WINS_KEY], reverse=True)
        return sorted(sorted_players, key=lambda x: x[1][Strings.PLAYER_POINTS_KEY], reverse=True)

    async def _pop_queue(self, ctx: Context, six_mans_queue: SixMansQueue):
        game = await self._create_game(ctx.guild, six_mans_queue)
        if game is None:
            return False
        
        #Remove players from any other queue they were in
        for player in game.players:
            for queue in self.queues:
                if player in queue.queue:
                    await self._remove_from_queue(player, queue)
        
        # Notify all players that queue has popped
        # await game.textChannel.send("{}\n".format(", ".join([player.mention for player in game.players])))

        self.games.append(game)
        await self._save_games(ctx.guild, self.games)
        return True

    async def _create_game(self, guild: discord.Guild, six_mans_queue: SixMansQueue):
        if not six_mans_queue._queue_full():
            return None
        players = [six_mans_queue._get() for _ in range(self.queueMaxSize)]

        await six_mans_queue.send_message(message="**Queue is full! Game is being created.**")

        game = Game(
            players,
            six_mans_queue,
            helper_role=await self._helper_role(guild),
            automove=await self._get_automove(guild),
            observers=self.observers
        )
        await game.create_game_channels(await self._category(guild))
        await game.process_team_selection_method()
        return game

    async def _get_info(self, ctx: Context):
        game = self._get_game_by_text_channel(ctx.channel)
        if game is None:
            await ctx.send(":x: This command can only be used in a {} Mans game channel.".format(self.queueMaxSize))
            return None

        for queue in self.queues:
            if queue.id == game.queue.id:
                return game, queue

        await ctx.send(":x: Queue not found for this channel, please message an Admin if you think this is a mistake.")
        return None

    def is_valid_ts(self, team_selection):
        for ts in QTS_METHODS:
            if team_selection.lower() == ts.lower():
                return ts
        return None

    # adds observer
    def add_observer(self, observer):
        if observer not in self.observers:
            self.observers.add(observer)

    def remove_observer(self, observer):
        while observer in self.observers:
            self.observers.remove(observer)

    def _get_game_and_queue(self, channel: discord.TextChannel):
        game = self._get_game_by_text_channel(channel)
        if game:
            return game, game.queue
        else:
            return None, None

    def _get_game_by_text_channel(self, channel: discord.TextChannel):
        for game in self.games:
            if game.textChannel == channel:
                return game

    def _get_queue_by_text_channel(self, channel: discord.TextChannel):
        for six_mans_queue in self.queues:
            for queuechannel in six_mans_queue.channels:
                if queuechannel == channel:
                    return six_mans_queue

    def _get_queue_name(self, guild: discord.Guild, queue_name):
        if queue_name is None:
            return guild.name
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

#endregion

#region embed and string format methods

    def embed_player_added(self, player: discord.Member, six_mans_queue: SixMansQueue):
        player_list = self.format_player_list(six_mans_queue)
        embed = discord.Embed(color=discord.Colour.green())
        embed.set_author(name="{0} added to the {1} queue. ({2}/{3})".format(player.display_name, six_mans_queue.name,
            six_mans_queue.queue.qsize(), self.queueMaxSize), icon_url="{}".format(player.avatar_url))
        embed.add_field(name="Players in Queue", value=player_list, inline=False)
        return embed

    def embed_player_removed(self, player: discord.Member, six_mans_queue: SixMansQueue):
        player_list = self.format_player_list(six_mans_queue)
        embed = discord.Embed(color=discord.Colour.red())
        embed.set_author(name="{0} removed from the {1} queue. ({2}/{3})".format(player.display_name, six_mans_queue.name,
            six_mans_queue.queue.qsize(), self.queueMaxSize), icon_url="{}".format(player.avatar_url))
        embed.add_field(name="Players in Queue", value=player_list, inline=False)
        return embed

    def embed_queue_info(self, queue: SixMansQueue):
        embed = discord.Embed(title="{0} {1} Mans Info".format(queue.name, self.queueMaxSize), color=discord.Colour.blue())
        embed.add_field(name="Team Selection", value=queue.teamSelection, inline=False)
        embed.add_field(name="Channels", value="{}\n".format(", ".join([channel.mention for channel in queue.channels])), inline=False)
        embed.add_field(name="Games Played", value="{}\n".format(queue.gamesPlayed), inline=False)
        embed.add_field(name="Unique Players All-Time", value="{}\n".format(len(queue.players)), inline=False)
        embed.add_field(name="Point Breakdown", value="**Per Series Played:** {0}\n**Per Series Win:** {1}"
            .format(queue.points[Strings.PP_PLAY_KEY], queue.points[Strings.PP_WIN_KEY]), inline=False)
        return embed

    def embed_queue_players(self, queue: SixMansQueue):
        player_list = self.format_player_list(queue)
        embed = discord.Embed(title="{0} {1} Mans Queue".format(queue.name, self.queueMaxSize), color=discord.Colour.blue())
        embed.add_field(name="Players in Queue", value=player_list, inline=False)
        return embed

    def embed_active_games(self, queueGames: Dict[int, List[Game]]):
        embed = discord.Embed(title="{0} Mans Active Games".format(self.queueMaxSize), color=discord.Colour.blue())
        for queueId in queueGames.keys():
            games = queueGames[queueId]
            queueName = next(queue.name for queue in self.queues if queue.id == queueId)
            embed.add_field(name="{}:".format(queueName), value="{}".format("\n".join(["{0}\n{1}".format(str(game.id), ", ".join([player.mention for player in game.players])) for game in games])), inline=False)
        return embed

    async def embed_leaderboard(self, ctx: Context, sorted_players, queue_name, games_played, lb_format):
        embed = discord.Embed(title="{0} {1} Mans {2} Leaderboard".format(queue_name, self.queueMaxSize, lb_format), color=discord.Colour.blue())
        embed.add_field(name="Games Played", value="{}\n".format(games_played), inline=True)
        embed.add_field(name="Unique Players", value="{}\n".format(len(sorted_players)), inline=True)
        embed.add_field(name="⠀", value="⠀", inline=True) # Blank field added to push the Player and Stats fields to a new line
        
        index = 1
        playerStrings = []
        statStrings = []
        for player in sorted_players:
            try:
                member: discord.Member = await commands.MemberConverter().convert(ctx, player[0])
            except:
                await ctx.send(":x: Can't find player with id: {}".format(player[0]))
                return

            player_info = player[1]
            playerStrings.append("`{0}` **{1:25s}:**".format(index, member.display_name))
            statStrings.append("Points: `{0:4d}`  Wins: `{1:3d}`  Games Played: `{2:3d}`".format(player_info[Strings.PLAYER_POINTS_KEY],
                player_info[Strings.PLAYER_WINS_KEY], player_info[Strings.PLAYER_GP_KEY]))
            
            index += 1
            if index > 10:
                break
        
        author = ctx.author
        try:
            author_index = [y[0] for y in sorted_players].index("{0}".format(author.id))
            if author_index is not None and author_index > 9:
                author_info = sorted_players[author_index][1]
                playerStrings.append("\n`{0}` **{1:25s}:**".format(author_index + 1, author.display_name))
                statStrings.append("\nPoints: `{0:4d}`  Wins: `{1:3d}`  Games Played: `{2:3d}`".format(author_info[Strings.PLAYER_POINTS_KEY],
                author_info[Strings.PLAYER_WINS_KEY], author_info[Strings.PLAYER_GP_KEY]))
        except Exception:
            pass

        embed.add_field(name="Player", value="{}\n".format("\n".join(playerStrings)), inline=True)
        embed.add_field(name="Stats", value="{}\n".format("\n".join(statStrings)), inline=True)
        return embed

    def embed_rank(self, player, sorted_players, queue_name, rank_format):
        try:
            num_players = len(sorted_players)
            points_index = [y[0] for y in sorted_players].index("{0}".format(player.id))
            player_info = sorted_players[points_index][1]
            points, wins, games_played = player_info[Strings.PLAYER_POINTS_KEY], player_info[Strings.PLAYER_WINS_KEY], player_info[Strings.PLAYER_GP_KEY]
            wins_index = [y[0] for y in sorted(sorted_players, key=lambda x: x[1][Strings.PLAYER_WINS_KEY], reverse=True)].index("{0}".format(player.id))
            games_played_index = [y[0] for y in sorted(sorted_players, key=lambda x: x[1][Strings.PLAYER_GP_KEY], reverse=True)].index("{0}".format(player.id))
            embed = discord.Embed(title="{0} {1} {2} Mans {3} Rank".format(player.display_name, queue_name, self.queueMaxSize, rank_format), color=discord.Colour.blue())
            embed.set_thumbnail(url=player.avatar_url)
            embed.add_field(name="Points:", value="**Value:** {2} | **Rank:** {0}/{1}".format(points_index + 1, num_players, points), inline=True)
            embed.add_field(name="Wins:", value="**Value:** {2} | **Rank:** {0}/{1}".format(wins_index + 1, num_players, wins), inline=True)
            embed.add_field(name="Games Played:", value="**Value:** {2} | **Rank:** {0}/{1}".format(games_played_index + 1, num_players, games_played), inline=True)
        except:
            embed = discord.Embed(title="{0} {1} {2} Mans {3} Rank".format(player.display_name, queue_name, self.queueMaxSize, rank_format), color=discord.Colour.red(),
                description="No stats yet to rank {}".format(player.mention))
            embed.set_thumbnail(url=player.avatar_url)
        return embed

    def format_player_list(self, queue: SixMansQueue):
        player_list = "{}".format(", ".join([player.mention for player in queue.queue.queue]))
        if player_list == "":
            player_list = "No players currently in the queue"
        return player_list

#endregion

#region load/save methods

    async def _pre_load_queues(self, guild: discord.Guild):
        if self.queues is None or self.queues == [] or self.queues[0].guild != guild:
            queues = await self._queues(guild)
            self.queues = []
            default_team_selection = await self._team_selection(guild)
            for key, value in queues.items():
                queue_channels = [guild.get_channel(x) for x in value["Channels"]]
                queue_name = value["Name"]
                team_selection = value["TeamSelection"] if "TeamSelection" in value else default_team_selection
                six_mans_queue = SixMansQueue(queue_name, guild, queue_channels, value["Points"], value["Players"], value["GamesPlayed"], self.queueMaxSize, team_selection)
                six_mans_queue.id = int(key)
                self.queues.append(six_mans_queue)

    async def _pre_load_games(self, guild: discord.Guild):
        await self._pre_load_queues(guild)
        category = await self._category(guild)
        if self.games is None or self.games == [] or self.games[0].queue.guild != guild:
            games = await self._games(guild)
            game_list = []
            for key, value in games.items():
                players = [guild.get_member(x) for x in value["Players"]]
                text_channel = guild.get_channel(value["TextChannel"])
                voice_channels = [guild.get_channel(x) for x in value["VoiceChannels"]]
                queueId = value["QueueId"]

                queue = None
                for q in self.queues:
                    if q.id == queueId:
                        queue = q
                        
                game = Game(players, queue, text_channel=text_channel, voice_channels=voice_channels, observers=self.observers)
                game.id = int(key)
                game.captains = [guild.get_member(x) for x in value["Captains"]]
                game.blue = set([guild.get_member(x) for x in value["Blue"]])
                game.orange = set([guild.get_member(x) for x in value["Orange"]])
                game.roomName = value["RoomName"]
                game.roomPass = value["RoomPass"]
                try:
                    game.info_message = await game.textChannel.fetch_message(value["InfoMessage"])
                    game.teamSelection = value["TeamSelection"]
                except:
                    game.teamSelection = game.queue.teamSelection
                    await game.process_team_selection_method()
                game.scoreReported = value["ScoreReported"]
                game_list.append(game)

            self.games = game_list

    async def _games(self, guild: discord.Guild):
        return await self.config.guild(guild).Games()

    async def _save_games(self, guild: discord.Guild, games: List[Game]):
        game_dict = {}
        for game in games:
            game_dict[game.id] = game._to_dict()
        await self.config.guild(guild).Games.set(game_dict)

    async def _queues(self, guild: discord.Guild):
        return await self.config.guild(guild).Queues()

    async def _save_queues(self, guild: discord.Guild, queues: List[SixMansQueue]):
        queue_dict = {}
        for queue in queues:
            if queue.guild == guild:
                queue_dict[queue.id] = queue._to_dict()
        await self.config.guild(guild).Queues.set(queue_dict)

    async def _scores(self, guild: discord.Guild):
        return await self.config.guild(guild).Scores()

    async def _save_scores(self, guild: discord.Guild, scores):
        await self.config.guild(guild).Scores.set(scores)

    async def _games_played(self, guild: discord.Guild):
        return await self.config.guild(guild).GamesPlayed()

    async def _save_games_played(self, guild: discord.Guild, games_played: int):
        await self.config.guild(guild).GamesPlayed.set(games_played)

    async def _players(self, guild: discord.Guild):
        return await self.config.guild(guild).Players()

    async def _save_players(self, guild: discord.Guild, players):
        await self.config.guild(guild).Players.set(players)

    async def _get_automove(self, guild: discord.Guild):
        return await self.config.guild(guild).AutoMove()

    async def _save_automove(self, guild: discord.Guild, automove: bool):
        await self.config.guild(guild).AutoMove.set(automove)

    async def _category(self, guild: discord.Guild):
        return guild.get_channel(await self.config.guild(guild).CategoryChannel())

    async def _save_category(self, guild: discord.Guild, category):
        await self.config.guild(guild).CategoryChannel.set(category)

    async def _save_q_lobby_vc(self, guild: discord.Guild, vc):
        await self.config.guild(guild).QLobby.set(vc)
    
    async def _get_q_lobby_vc(self, guild: discord.Guild):
        lobby_voice = await self.config.guild(guild).QLobby()
        for vc in guild.voice_channels:
            if vc.id == lobby_voice:
                return vc
        return None

    async def _helper_role(self, guild: discord.Guild):
        return guild.get_role(await self.config.guild(guild).HelperRole())

    async def _save_helper_role(self, guild: discord.Guild, helper_role):
        await self.config.guild(guild).HelperRole.set(helper_role)

    async def _save_team_selection(self, guild: discord.Guild, team_selection):
        await self.config.guild(guild).DefaultTeamSelection.set(team_selection)
    
    async def _team_selection(self, guild: discord.Guild):
        return await self.config.guild(guild).DefaultTeamSelection()

#endregion
