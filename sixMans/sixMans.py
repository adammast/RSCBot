import asyncio
import datetime
import random
from sys import exc_info, maxsize
from typing import Dict, List

import discord
from discord.ext.commands import Context
from redbot.core import Config, checks, commands
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

from .game import Game
from .queue import SixMansQueue
from .strings import Strings

DEBUG = False
MINIMUM_GAME_TIME = 600                         # Seconds (10 Minutes)
PLAYER_TIMEOUT_TIME = 10 if DEBUG else 14400    # How long players can be in a queue in seconds (4 Hours)
LOOP_TIME = 5                                   # How often to check the queues in seconds
VERIFY_TIMEOUT = 15                             # How long someone has to react to a prompt (seconds)
CHANNEL_SLEEP_TIME = 5 if DEBUG else 30         # How long channels will persist after a game's score has been reported (seconds)

QTS_METHODS = [
    Strings.VOTE_TS,
    Strings.CAPTAINS_TS,
    Strings.RANDOM_TS,
    Strings.BALANCED_TS,
    Strings.SELF_PICKING_TS
]  # , Strings.SHUFFLE_TS, Strings.BALANCED_TS]
defaults = {
    "CategoryChannel": None,
    "HelperRole": None,
    "AutoMove": False,
    "ReactToVote": True,
    "QLobby": None,
    "DefaultTeamSelection": Strings.RANDOM_TS,
    "DefaultQueueMaxSize": 6,
    "PlayerTimeout": PLAYER_TIMEOUT_TIME,
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
        self.queues: dict[list[SixMansQueue]] = {}
        self.games: dict[list[Game]] = {}
        self.queueMaxSize: dict[int] = {}
        self.player_timeout_time: dict[int] = {}

        asyncio.create_task(self._pre_load_data())
        self.timeout_tasks = {}
        self.observers = set()
        
    def cog_unload(self):
        """Clean up when cog shuts down."""
        for player, tasks in self.timeout_tasks.items():
            for queue, timeout_task in tasks.items():
                timeout_task.cancel()

#region commmands

    #region admin commands
    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearSixMansData(self, ctx: Context):
        msg = await ctx.send("{0} Please verify that you wish to clear **all** of the {1} Mans data for the guild.".format(ctx.author.mention, self.queueMaxSize[ctx.guild]))
        start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)

        pred = ReactionPredicate.yes_or_no(msg, ctx.author)
        await ctx.bot.wait_for("reaction_add", check=pred)
        if pred.result:
            # await self.config.clear_all_guilds()
            await self._clear_all_data(ctx.guild)
            await ctx.send("Done")
        else:
            await ctx.send(":x: Data **not** cleared.")

    #region admin commands
    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def preLoadData(self, ctx: Context):
        """Reloads all data for the 6mans cog"""
        await self._pre_load_data()
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def addNewQueue(self, ctx: Context, name, points_per_play: int, points_per_win: int, *channels):
        queue_channels = []
        for channel in channels:
            queue_channels.append(await commands.TextChannelConverter().convert(ctx, channel))
        for queue in self.queues[ctx.guild]:
            if queue.name == name:
                await ctx.send(":x: There is already a queue set up with the name: {0}".format(name))
                return
            for channel in queue_channels:
                if channel in queue.channels:
                    await ctx.send(":x: {0} is already being used for queue: {1}".format(channel.mention, queue.name))
                    return
        queue_max_size = await self._get_queue_max_size(ctx.guild)
        points = {Strings.PP_PLAY_KEY: points_per_play, Strings.PP_WIN_KEY: points_per_win}
        team_selection = await self._team_selection(ctx.guild)
        six_mans_queue = SixMansQueue(name, ctx.guild, queue_channels, points, {}, 0, queue_max_size, teamSelection=team_selection, category=await self._category(ctx.guild))
        self.queues[ctx.guild].append(six_mans_queue)
        await self._save_queues(ctx.guild, self.queues[ctx.guild])
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def editQueue(self, ctx: Context, current_name, new_name, points_per_play: int, points_per_win: int, *channels):
        six_mans_queue = None
        for queue in self.queues[ctx.guild]:
            if queue.name == current_name:
                six_mans_queue = queue
                break

        if six_mans_queue is None:
            await ctx.send(":x: No queue found with name: {0}".format(current_name))
            return

        queue_channels = []
        for channel in channels:
            queue_channels.append(await commands.TextChannelConverter().convert(ctx, channel))
        for queue in self.queues[ctx.guild]:
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
        await self._save_queues(ctx.guild, self.queues[ctx.guild])
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command(aliases=['setQTS', 'setQueueTeamSelection', 'sqts'])
    @checks.admin_or_permissions()
    async def setQueueTS(self, ctx: Context, queue_name, *, team_selection):
        """Sets the team selection mode for a specific queue"""
        if not await self.has_perms(ctx.author):
            return

        six_mans_queue = None
        for queue in self.queues[ctx.guild]:
            if queue.name == queue_name:
                six_mans_queue = queue
                break

        if six_mans_queue is None:
            await ctx.send(":x: No queue found with name: {0}".format(queue_name))
            return
        
        valid_ts = self.is_valid_ts(team_selection)
        if valid_ts:
            await six_mans_queue.set_team_selection(valid_ts)
            await self._save_queues(ctx.guild, self.queues[ctx.guild])
            await ctx.send("Done")
        else:
            await ctx.send(":x: **{}** is not a valid team selection method.".format(team_selection))

    @commands.guild_only()
    @commands.command(aliases=['setQTimeout', 'setQTO', 'sqto'])
    @checks.admin_or_permissions()
    async def setQueueTimeout(self, ctx: Context, minutes: int):
        """Sets the player timeout in minutes for queues in the guild (Default: 240) ."""
        seconds = minutes*60
        await self._save_player_timeout(ctx.guild, seconds)
        self.player_timeout_time[ctx.guild] = seconds
        s_if_plural = "" if minutes == 1 else "s"
        await ctx.send(":white_check_mark: Players in Six Mans Queues will now be timed out after **{} minute{}**.".format(minutes, s_if_plural))
        
    @commands.guild_only()
    @commands.command(aliases=['getQTO', 'gqto', 'qto'])
    async def getQueueTimeout(self, ctx: Context):
        """Gets the player timeout in minutes for queues in the guild (Default: 240)."""
        seconds = await self._player_timeout(ctx.guild)
        minutes = seconds//60
        s_if_plural = "" if minutes == 1 else "s"
        await ctx.send("Players in Six Mans Queues are timed out after **{} minute{}**.".format(minutes, s_if_plural))
    
    @commands.guild_only()
    @commands.command(aliases=['setQueueSize', 'setQMaxSize', 'setQMS', 'sqms'])
    @checks.admin_or_permissions()
    async def setQueueMaxSize(self, ctx: Context, max_size: int):
        """Sets the max size for all queues in the guild. (Default: 6)"""
        if max_size <= 2:
            return await ctx.send(":x: Queues sizes must be 4+.")
        if max_size % 2 == 1:
            return await ctx.send(":x: Queues sizes must be configured for an even number of players.")
        
        for queue in self.queues[ctx.guild]:
            queue.maxSize = max_size
        
        await self._save_queues(ctx.guild, self.queues[ctx.guild])
        await self._save_queue_max_size(ctx.guild, max_size)
        await ctx.send("Done")
    
    @commands.guild_only()
    @commands.command(aliases=['getQMaxSize', 'getQMS', 'gqms', 'qms'])
    @checks.admin_or_permissions()
    async def getQueueMaxSize(self, ctx: Context):
        """Gets the max size for all queues in the guild. (Default: 6)"""
        guild_queue_size = await self._get_queue_max_size(ctx.guild)
        await ctx.send("Default Queue Size: {}".format(guild_queue_size))

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def removeQueue(self, ctx: Context, *, queue_name):
        for queue in self.queues[ctx.guild]:
            if queue.name == queue_name:
                self.queues[ctx.guild].remove(queue)
                await self._save_queues(ctx.guild, self.queues[ctx.guild])
                await ctx.send("Done")
                return
        await ctx.send(":x: No queue set up with name: {0}".format(queue_name))

    @commands.guild_only()
    @commands.command(aliases=["qm", "queueAll", "qa", "forceQueue", "fq"])
    @checks.admin_or_permissions(manage_guild=True)
    async def queueMultiple(self, ctx: Context, *members: discord.Member):
        """Mass queueing for testing purposes"""
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

        six_mans_queue = self._get_queue_by_text_channel(ctx.channel)
        if player in six_mans_queue.queue:
            await self._remove_from_queue(player, six_mans_queue)
        else:
            await ctx.send("{} is not in queue.".format(player.display_name))

    # team selection
    @commands.guild_only()
    @commands.command(aliases=["fts"])
    async def forceTeamSelection(self, ctx, *, args):
        """Forces a popped queue to restart a specified team selection.
        
        Format: `[p]fts <team_selection> [game_id]`"""
        if not await self.has_perms(ctx.author):
            return

        if len(args) == 1:
            game_id = None
            team_selection = args
        elif len(args) > 1:
            args = args.split()
            try:
                game_id = int(args[-1])
                team_selection = ' '.join(args[0:-1])
            except:
                game_id = None
                team_selection = ' '.join(args)

        game: Game = None
        if game_id:
            for active_game in self.games[ctx.guild]:
                if active_game.id == game_id:
                    game = active_game
        else:
            game = self._get_game_by_text_channel(ctx.channel)
        
        if not game:
            await ctx.send(":x: Game not found.")
            return

        valid_ts = self.is_valid_ts(team_selection)
        if not valid_ts:
            return await ctx.send(":x: **{}** is not a valid team selection method.".format(team_selection))

        await game.textChannel.send("Processing Forced Team Selection: {}".format(valid_ts))
        game.teamSelection = valid_ts
        await game.process_team_selection_method(team_selection=valid_ts)

    @commands.guild_only()
    @commands.command(aliases=["fcg"])
    async def forceCancelGame(self, ctx: Context, gameId: int = None):
        """Cancel the current game. Can only be used in a game channel unless a gameId is given.
        The game will end with no points given to any of the players. The players with then be allowed to queue again."""
        if not await self.has_perms(ctx.author):
            return
        
        game = None
        if gameId is None:
            game = self._get_game_by_text_channel(ctx.channel)
            if game is None:
                await ctx.send(":x: This command can only be used in a {} Mans game channel.".format(self.queueMaxSize[ctx.guild]))
                return
        else:
            pass

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
        if ctx.message.channel.category != await self._category(ctx.guild):
            return False

        game = self._get_game_by_text_channel(ctx.channel)
        player = ctx.message.author
        if game:
            # try:
            embed = discord.Embed(
                title="{0} {1} Mans Game Info".format(game.queue.name, game.queue.maxSize),
                color=discord.Colour.green()
            )
            embed.set_thumbnail(url=ctx.guild.icon_url)
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
        six_mans_queue = self._get_queue_by_text_channel(ctx.channel)
        player = ctx.message.author

        if player in six_mans_queue.queue.queue:
            await ctx.send(":x: You are already in the {0} queue".format(six_mans_queue.name))
            return
        for game in self.games[ctx.guild]:
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
        game = self._get_game_by_text_channel(ctx.channel)
        if game is None:
            await ctx.send(":x: This command can only be used in a {} Mans game channel.".format(self.queueMaxSize[ctx.guild]))
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

    # team selection
    @commands.guild_only()
    @commands.command(aliases=["r", "random"])
    async def voteRandom(self, ctx):
        game = self._get_game_by_text_channel(ctx.channel)
        ignore_call = (
            await self._is_react_to_vote(ctx.guild)
            or not game or game.teamSelection != Strings.VOTE_TS or game.state != Strings.TEAM_SELECTION_GS
        )
        if ignore_call:
            return

    @commands.guild_only()
    @commands.command(aliases=["c", "votecaptains", "vc"])
    async def voteCaptains(self, ctx):
        game = self._get_game_by_text_channel(ctx.channel)
        ignore_call = (
            await self._is_react_to_vote(ctx.guild)
            or not game or game.teamSelection != Strings.VOTE_TS or game.state != Strings.TEAM_SELECTION_GS
        )
        if ignore_call:
            return

    @commands.guild_only()
    @commands.command(aliases=["b", "balanced", "vb"])
    async def voteBalanced(self, ctx):
        game = self._get_game_by_text_channel(ctx.channel)
        ignore_call = (
            await self._is_react_to_vote(ctx.guild)
            or not game or game.teamSelection != Strings.VOTE_TS or game.state != Strings.TEAM_SELECTION_GS
        )
        if ignore_call:
            return

    @commands.guild_only()
    @commands.command(aliases=["s", "spt", "selfPickingTeams", "vs"])
    async def voteSelfPickingTeams(self, ctx):
        game = self._get_game_by_text_channel(ctx.channel)
        ignore_call = (
            await self._is_react_to_vote(ctx.guild)
            or not game or game.teamSelection != Strings.VOTE_TS or game.state != Strings.TEAM_SELECTION_GS
        )
        if ignore_call:
            return

    #endregion player commands

    #region listeners
    @commands.Cog.listener("on_reaction_add")
    async def on_reaction_add(self, reaction, user):
        return
        channel = reaction.message.channel
        if type(channel) == discord.DMChannel:
            return
        await self.process_six_mans_reaction_add(reaction.message, channel, user, reaction.emoji) 

    @commands.Cog.listener("on_raw_reaction_add")
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        channel = self.bot.get_channel(payload.channel_id)
        if type(channel) == discord.DMChannel:
            return

        message = await channel.fetch_message(payload.message_id)
        user = self.bot.get_user(payload.user_id)
        if not user:
            user = await self.bot.fetch_user(payload.user_id)
        
        
        await self.process_six_mans_reaction_add(message, channel, user, payload.emoji)

    @commands.Cog.listener("on_reaction_remove")
    async def on_reaction_remove(self, reaction, user):
        return
        if type(reaction.message.channel) == discord.DMChannel:
            return

        await self.process_six_mans_reaction_removed(reaction.message.channel, user, reaction.emoji)

    @commands.Cog.listener("on_raw_reaction_remove")
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        channel = self.bot.get_channel(payload.channel_id)
        if type(channel) == discord.DMChannel:
            return

        user = self.bot.get_user(payload.user_id)
        if not user:
            user = await self.bot.fetch_user(payload.user_id)

        await self.process_six_mans_reaction_removed(channel, user, payload.emoji)

    @commands.Cog.listener("on_guild_channel_delete")
    async def on_guild_channel_delete(self, channel):
        """If a queue channel is deleted, removes it from the queue class instance. If the last queue channel is deleted, the channel is replaced."""
        #TODO: Error catch if Q Lobby VC is deleted
        if type(channel) != discord.TextChannel:
            return
        queue = None
        for queue in self.queues[channel.guild]:
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
        await self._save_queues(channel.guild, self.queues[ctx.guild])

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
        players = None
        queue = await self._get_queue_by_name(ctx.guild, queue_name) if queue_name else None
        
        if queue:
            queue_name = queue.name
            players = queue.players
            games_played = queue.gamesPlayed
        else:
            players = await self._players(ctx.guild)
            queue_name = ctx.guild.name
            games_played = await self._games_played(ctx.guild)

        if not players:
            await ctx.send(":x: Queue leaderboard not available for {0}".format(queue_name))
            return

        sorted_players = self._sort_player_dict(players)
        await ctx.send(embed=await self.embed_leaderboard(ctx, sorted_players, queue, games_played, "All-time"))

    @commands.guild_only()
    @queueLeaderBoard.command(aliases=["daily"])
    async def day(self, ctx: Context, *, queue_name: str = None):
        """Daily leader board. All games from the last 24 hours will count"""
        scores = await self._scores(ctx.guild)

        queue = await self._get_queue_by_name(ctx.guild, queue_name) if queue_name else None
        queue_id = queue.id if queue else None
        queue_name = queue.name if queue else ctx.guild.name
        day_ago = datetime.datetime.now() - datetime.timedelta(days=1)
        players, games_played = self._filter_scores(ctx.guild, scores, day_ago, queue_id)

        if not players:
            await ctx.send(":x: Queue leaderboard not available for {0}".format(queue_name))
            return

        sorted_players = self._sort_player_dict(players)
        await ctx.send(embed=await self.embed_leaderboard(ctx, sorted_players, queue, games_played, "Daily"))

    @commands.guild_only()
    @queueLeaderBoard.command(aliases=["weekly", "wk"])
    async def week(self, ctx: Context, *, queue_name: str = None):
        """Weekly leader board. All games from the last week will count"""
        scores = await self._scores(ctx.guild)

        queue = await self._get_queue_by_name(ctx.guild, queue_name) if queue_name else None
        queue_id = queue.id if queue else None
        week_ago = datetime.datetime.now() - datetime.timedelta(weeks=1)
        players, games_played = self._filter_scores(ctx.guild, scores, week_ago, queue_id)

        if not players:
            await ctx.send(":x: Queue leaderboard not available for {0}".format(queue_name))
            return

        queue_name = queue.name if queue else ctx.guild.name
        sorted_players = self._sort_player_dict(players)
        await ctx.send(embed=await self.embed_leaderboard(ctx, sorted_players, queue, games_played, "Weekly"))

    @commands.guild_only()
    @queueLeaderBoard.command(aliases=["monthly", "mnth"])
    async def month(self, ctx: Context, *, queue_name: str = None):
        """Monthly leader board. All games from the last 30 days will count"""
        scores = await self._scores(ctx.guild)

        queue = await self._get_queue_by_name(ctx.guild, queue_name) if queue_name else None
        queue_id = queue.id if queue else None
        month_ago = datetime.datetime.now() - datetime.timedelta(days=30)
        players, games_played = self._filter_scores(ctx.guild, scores, month_ago, queue_id)

        if not players:
            await ctx.send(":x: Queue leaderboard not available for {0}".format(queue_name))
            return

        queue_name = queue.name if queue else ctx.guild.name
        sorted_players = self._sort_player_dict(players)
        await ctx.send(embed=await self.embed_leaderboard(ctx, sorted_players, queue_name, games_played, "Monthly"))

    #endregion

    #region rank commands

    @commands.guild_only()
    @commands.group(aliases=["rnk", "playerCard", "pc"])
    async def rank(self, ctx: Context):
        """Get your rank in points, wins, and games played for the specific queue. If no queue name is given it will show your overall rank across all queues."""

    @commands.guild_only()
    @rank.command(aliases=["all-time", "overall"])
    async def alltime(self, ctx: Context, player: discord.Member = None, *, queue_name: str = None):
        """All-time ranks"""
        queue = None
        if queue_name:
            queue = await self._get_queue_by_name(ctx.guild, queue_name)
            players = queue.players
        else:
            players = await self._players(ctx.guild)
            queue_name = ctx.guild.name

        if not players:
            await ctx.send(":x: Player ranks not available for {0}".format(queue_name))
            return

        queue_max_size = queue.maxSize if queue else self.queueMaxSize[ctx.guild]
        sorted_players = self._sort_player_dict(players)
        player = player if player else ctx.author
        await ctx.send(embed=self.embed_rank(player, sorted_players, queue_name, queue_max_size, "All-time"))

    @commands.guild_only()
    @rank.command(aliases=["day"])
    async def daily(self, ctx: Context, player: discord.Member = None, *, queue_name: str = None):
        """Daily ranks. All games from the last 24 hours will count"""
        scores = await self._scores(ctx.guild)

        queue = await self._get_queue_by_name(ctx.guild, queue_name) if queue_name else None
        queue_id = queue.id if queue else None
        day_ago = datetime.datetime.now() - datetime.timedelta(days=1)
        players = self._filter_scores(ctx.guild, scores, day_ago, queue_id)[0]
        queue_name = queue.name if queue else ctx.guild.name
        
        if not players:
            await ctx.send(":x: Player ranks not available for {0}".format(queue_name))
            return

        queue_max_size = queue.maxSize if queue else self.queueMaxSize[ctx.guild]
        sorted_players = self._sort_player_dict(players)
        player = player if player else ctx.author
        await ctx.send(embed=self.embed_rank(player, sorted_players, queue_name, queue_max_size, "Daily"))

    @commands.guild_only()
    @rank.command(aliases=["week", "wk"])
    async def weekly(self, ctx: Context, player: discord.Member = None, *, queue_name: str = None):
        """Weekly ranks. All games from the last week will count"""
        scores = await self._scores(ctx.guild)

        queue = await self._get_queue_by_name(ctx.guild, queue_name) if queue_name else None
        queue_id = queue.id if queue else None
        week_ago = datetime.datetime.now() - datetime.timedelta(weeks=1)
        players = self._filter_scores(ctx.guild, scores, week_ago, queue_id)[0]
        queue_name = queue.name if queue else ctx.guild.name

        if not players:
            await ctx.send(":x: Player ranks not available for {0}".format(queue_name))
            return

        queue_max_size = queue.maxSize if queue else self.queueMaxSize[ctx.guild]
        sorted_players = self._sort_player_dict(players)
        player = player if player else ctx.author
        await ctx.send(embed=self.embed_rank(player, sorted_players, queue_name, queue_max_size, "Weekly"))

    @commands.guild_only()
    @rank.command(aliases=["month", "mnth"])
    async def monthly(self, ctx: Context, player: discord.Member = None, *, queue_name: str = None):
        """Monthly ranks. All games from the last 30 days will count"""
        scores = await self._scores(ctx.guild)

        queue = await self._get_queue_by_name(ctx.guild, queue_name) if queue_name else None
        queue_id = queue.id if queue else None
        month_ago = datetime.datetime.now() - datetime.timedelta(days=30)
        players = self._filter_scores(ctx.guild, scores, month_ago, queue_id)[0]
        queue_name = queue.name if queue else ctx.guild.name

        if not players:
            await ctx.send(":x: Player ranks not available for {0}".format(queue_name))
            return

        queue_max_size = queue.maxSize if queue else self.queueMaxSize[ctx.guild]
        sorted_players = self._sort_player_dict(players)
        player = player if player else ctx.author
        await ctx.send(embed=self.embed_rank(player, sorted_players, queue_name, queue_max_size, "Monthly"))

    #endregion

    #region get and set commands

    @commands.guild_only()
    @commands.command(aliases=["cq", "status"])
    async def checkQueue(self, ctx: Context):
        six_mans_queue = self._get_queue_by_text_channel(ctx.channel)
        if not six_mans_queue:
            await ctx.send(":x: No queue set up in this channel")
            return
        await ctx.send(embed=self.embed_queue_players(six_mans_queue))

    @commands.guild_only()
    @commands.command(aliases=["setQLobby", "setQVC"])
    @checks.admin_or_permissions(manage_guild=True)
    async def setQueueLobby(self, ctx: Context, lobby_voice: discord.VoiceChannel):
        #TODO: Consider having the queues save the Queue Lobby VC
        for queue in self.queues[ctx.guild]:
            queue.lobby_vc = lobby_voice
        await self._save_q_lobby_vc(ctx.guild, lobby_voice.id)
        await self._save_queues(ctx.guild, self.queues[ctx.guild])
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
        queue_names = ""
        for queue in self.queues[ctx.guild]:
            if queue.guild == ctx.guild:
                queue_names += "{0}\n".format(queue.name)
        await ctx.send("```Queues set up in server:\n{0}```".format(queue_names))

    @commands.guild_only()
    @commands.command(aliases=["qi"])
    async def getQueueInfo(self, ctx: Context, *, queue_name=None):
        if queue_name:
            for queue in self.queues[ctx.guild]:
                if queue.name.lower() == queue_name.lower():
                    await ctx.send(embed=self.embed_queue_info(queue))
                    return
            await ctx.send(":x: No queue set up with name: {0}".format(queue_name))
            return

        six_mans_queue = self._get_queue_by_text_channel(ctx.channel)
        if not six_mans_queue:
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
        message = "Popped {0} Mans queues **{1}** members to their team voice channel.".format(self.queueMaxSize[ctx.guild], action)
        await ctx.send(message)
    
    @commands.guild_only()
    @commands.command(aliases=['toggleReactToVote', 'tvm', 'trtv'])
    @checks.admin_or_permissions(manage_guild=True)
    async def toggleVoteMethod(self, ctx: Context):
        """Toggles team selection voting method between commands and reactions."""
        react_to_vote = not await self._is_react_to_vote(ctx.guild)
        await self._save_react_to_vote(ctx.guild, react_to_vote)

        action = "reactions" if react_to_vote else "commands"
        message = "Members of popped {0} Mans queues will vote for team reactions with **{1}**.".format(self.queueMaxSize[ctx.guild], action)
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
        - **balanced (beta)**: creates balanced teams from all participating players
        - ~~**shuffle**: selects random teams, but allows re-shuffling teams after they have been set~~
        """
        # TODO: Support Captains [captains random, captains shuffle], Balanced
        team_selection_method = team_selection_method.title()
        if team_selection_method not in QTS_METHODS:
            return await ctx.send("**{}** is not a valid method of team selection.".format(team_selection_method))
        
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
        for queue in self.queues[ctx.guild]:
            queue.category = category_channel
        await self._save_category(ctx.guild, category_channel.id)
        await self._save_queues(ctx.guild, self.queues[ctx.guild])
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def getCategory(self, ctx: Context):
        """Gets the channel currently assigned as the transaction channel"""
        try:
            await ctx.send("{0} Mans category channel set to: {1}".format(self.queueMaxSize[ctx.guild], (await self._category(ctx.guild)).mention))
        except:
            await ctx.send(":x: {0} Mans category channel not set".format(self.queueMaxSize[ctx.guild]))

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
            await ctx.send("{0} Mans helper role set to: {1}".format(self.queueMaxSize[ctx.guild], (await self._helper_role(ctx.guild)).name))
        except:
            await ctx.send(":x: {0} mans helper role not set".format(self.queueMaxSize[ctx.guild]))

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

        queueGames: dict[int, list[Game]] = {}
        for game in self.games[ctx.guild]:
            queueGames.setdefault(game.queue.id, []).append(game)

        embed = self.embed_active_games(ctx.guild, queueGames)
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
        if member.guild_permissions.administrator:
            return True
        helper_role = await self._helper_role(member.guild)
        if helper_role and helper_role in member.roles:
            return True

    async def _add_to_queue(self, player: discord.Member, six_mans_queue: SixMansQueue):
        six_mans_queue._put(player)
        embed = self.embed_player_added(player, six_mans_queue)
        await six_mans_queue.send_message(embed=embed)
        await self.create_timeout_task(player, six_mans_queue, self.player_timeout_time[six_mans_queue.guild])

    async def _remove_from_queue(self, player: discord.Member, six_mans_queue: SixMansQueue):
        six_mans_queue._remove(player)
        embed = self.embed_player_removed(player, six_mans_queue)
        await six_mans_queue.send_message(embed=embed)
        await self.remove_timeout_task(player, six_mans_queue)

    async def get_visble_queue_channel(self, six_mans_queue: SixMansQueue, player: discord.Member):
        for channel in six_mans_queue.channels:
            if player in channel.members:
                return channel
        return None

    async def _auto_remove_from_queue(self, player: discord.Member, six_mans_queue: SixMansQueue):
        # Remove player from queue
        await self._remove_from_queue(player, six_mans_queue)
        
        # Send Player Message
        auto_remove_msg = (
            "You have been timed out from the **{} {} Mans queue**. You'll need to use the "
            + "queue command again if you wish to play some more."
        )
        auto_remove_msg = auto_remove_msg.format(six_mans_queue.name, six_mans_queue.maxSize)
        channel = await self.get_visble_queue_channel(six_mans_queue, player)

        try:
            invite_msg = "\n\nYou may return to {} to rejoin the queue!".format(channel.mention)
            embed = discord.Embed(
                title="{}: {} Mans Timeout".format(six_mans_queue.guild.name, six_mans_queue.maxSize),
                description=auto_remove_msg + invite_msg,
                color=discord.Color.red()
            )
            embed.set_thumbnail(url=six_mans_queue.guild.icon_url)
            await player.send(embed=embed)
        except:
            try:
                await player.send(auto_remove_msg)
            except:
                pass
    
    async def create_timeout_task(self, player: discord.Member, six_mans_queue: SixMansQueue, time=None):
        self.timeout_tasks.setdefault(player, {})
        self.timeout_tasks[player][six_mans_queue] = asyncio.create_task(self.player_queue_timeout(player, six_mans_queue, time))

    async def player_queue_timeout(self, player: discord.Member, six_mans_queue: SixMansQueue, time=None):
        if not time:
            time = self.player_queue_timeout[six_mans_queue.guild]

        await asyncio.sleep(time)
        try:
            await self._auto_remove_from_queue(player, six_mans_queue)
        except:
            pass

    async def cancel_timeout_task(self, player: discord.Member, six_mans_queue: SixMansQueue):
        try:
            self.timeout_tasks[player][six_mans_queue].cancel()
            await self.remove_timeout_task(player, six_mans_queue)
        except:
            pass
    
    async def remove_timeout_task(self, player: discord.Member, six_mans_queue: SixMansQueue):
        try:
            del self.timeout_tasks[player][six_mans_queue]
            if not self.timeout_tasks[player]:
                del self.timeout_tasks[player]
        except:
            pass
            
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
        await self._save_queues(guild, self.queues[guild])
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
        self.games[guild].remove(game)
        await self._save_games(guild, self.games[guild])
        await asyncio.sleep(CHANNEL_SLEEP_TIME)
        q_lobby_vc = await self._get_q_lobby_vc(guild)
        if not game.scoreReported:
            await game._notify(new_state=Strings.CANCELED_GS)
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

    def _filter_scores(self, guild, scores, start_date, queue_id):
        players = {}
        valid_scores = 0
        for score in scores:
            date_time = datetime.datetime.strptime(score["DateTime"], "%d-%b-%Y (%H:%M:%S.%f)")
            if  date_time > start_date and (queue_id is None or score["Queue"] == queue_id):
                self._give_points(players, score)
                valid_scores +=1
            else:
                break
        games_played = (valid_scores // self.queueMaxSize[guild])
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
            for queue in self.queues[ctx.guild]:
                if player in queue.queue:
                    await self._remove_from_queue(player, queue)
        
        # Notify all players that queue has popped
        # await game.textChannel.send("{}\n".format(", ".join([player.mention for player in game.players])))

        self.games[ctx.guild].append(game)
        await self._save_games(ctx.guild, self.games[ctx.guild])
        return True

    async def _create_game(self, guild: discord.Guild, six_mans_queue: SixMansQueue):
        if not six_mans_queue._queue_full():
            return None
        players = [six_mans_queue._get() for _ in range(six_mans_queue.maxSize)]

        await six_mans_queue.send_message(message="**Queue is full! Game is being created.**")

        game = Game(
            players,
            six_mans_queue,
            helper_role=await self._helper_role(guild),
            automove=await self._get_automove(guild),
            use_reactions=await self._is_react_to_vote(guild),
            observers=self.observers
        )
        await game.create_game_channels(await self._category(guild))
        await game.process_team_selection_method()
        return game

    async def _get_info(self, ctx: Context):
        game = self._get_game_by_text_channel(ctx.channel)
        if game is None:
            await ctx.send(":x: This command can only be used in a {} Mans game channel.".format(self.queueMaxSize[ctx.guild]))
            return None

        for queue in self.queues[ctx.guild]:
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
        for game in self.games[channel.guild]:
            if game.textChannel == channel:
                return game
        return None

    def _get_queue_by_text_channel(self, channel: discord.TextChannel):
        for six_mans_queue in self.queues[channel.guild]:
            for queuechannel in six_mans_queue.channels:
                if queuechannel == channel:
                    return six_mans_queue
        return None

    def _get_queue_by_name(self, guild: discord.Guild, queue_name):
        for queue in self.queues[guild]:
            if queue.name == queue_name:
                return queue
        return None

    async def process_six_mans_reaction_add(self, message: discord.Message, channel: discord.TextChannel, user: discord.User, emoji):
        # Note: This may be called TWICE both by on_reaction and/or on_raw_reaction
        if user.bot:
            return
        
        # on_raw_reaction_add
        if type(emoji) == discord.partial_emoji.PartialEmoji:
            emoji = emoji.name

        # Find Game
        game = self._get_game_by_text_channel(channel)
        game: Game
        if not game:
            return False
        if message != game.info_message:
            return False

        team_selection_mode = game.teamSelection.lower()

        if team_selection_mode == Strings.VOTE_TS.lower():
            await game.process_team_select_vote(emoji, user)

        elif team_selection_mode == Strings.CAPTAINS_TS.lower():
            await game.process_captains_pick(emoji, user)
        
        elif team_selection_mode == Strings.SELF_PICKING_TS.lower():
            await game.process_self_picking_teams(emoji, user, True)

        elif team_selection_mode == Strings.SHUFFLE_TS.lower():
            if emoji is not Strings.SHUFFLE_REACT:
                return
            
            # Check if Shuffle is enabled
            message = self.info_message
            now = datetime.datetime.utcnow()
            time_since_last_team = (now - message.created_at).seconds
            time_since_q_pop = (now - message.channel.created_at).seconds
            if time_since_q_pop > 300:
                return await channel.send(":x: Reshuffling teams is no longer permitted after 5 minutes of the initial team selection.")
            if time_since_last_team > 180:
                return await channel.send(":x: Reshuffling teams is only permitted for 3 minutes since the previous team selection.")

            count = len([reaction for reaction in message.reactions if reaction.emoji == emoji])
            shuffle_players = count >= int(len(game.players)/2)+1
            if shuffle_players:
                await channel.send("{} _Generating New teams..._".format(Strings.SHUFFLE_REACT))
                await game.shuffle_players()

    async def process_six_mans_reaction_removed(self, channel: discord.TextChannel, user: discord.User, emoji):
        # Note: This may be called TWICE both by on_reaction and/or on_raw_reaction
        if user.bot:
            return
        
        # on_raw_reaction_add
        if type(emoji) == discord.partial_emoji.PartialEmoji:
            emoji = emoji.name
        try:
            game = self._get_game_by_text_channel(channel)
            game: Game 
            if not game:
                return False

            if game.teamSelection.lower() == Strings.VOTE_TS.lower():
                await game.process_team_select_vote(emoji, user, added=False)
            
            elif game.teamSelection.lower() == Strings.SELF_PICKING_TS.lower():
                await game.process_self_picking_teams(emoji, user, False)
        except:
            pass

#endregion

#region embed and string format methods

    def embed_player_added(self, player: discord.Member, six_mans_queue: SixMansQueue):
        player_list = self.format_player_list(six_mans_queue)
        embed = discord.Embed(color=discord.Colour.green())
        embed.set_author(name="{0} added to the {1} queue. ({2}/{3})".format(player.display_name, six_mans_queue.name,
            six_mans_queue.queue.qsize(), six_mans_queue.maxSize), icon_url="{}".format(player.avatar_url))
        embed.add_field(name="Players in Queue", value=player_list, inline=False)
        return embed

    def embed_player_removed(self, player: discord.Member, six_mans_queue: SixMansQueue):
        player_list = self.format_player_list(six_mans_queue)
        embed = discord.Embed(color=discord.Colour.red())
        embed.set_author(name="{0} removed from the {1} queue. ({2}/{3})".format(player.display_name, six_mans_queue.name,
            six_mans_queue.queue.qsize(), six_mans_queue.maxSize), icon_url="{}".format(player.avatar_url))
        embed.add_field(name="Players in Queue", value=player_list, inline=False)
        return embed

    def embed_queue_info(self, queue: SixMansQueue):
        embed = discord.Embed(title="{0} {1} Mans Info".format(queue.name, queue.maxSize), color=discord.Colour.blue())
        emoji = queue.get_ts_emoji()
        if emoji:
            embed.add_field(name="Team Selection", value="{} {}".format(emoji, queue.teamSelection), inline=False)
        else:
            embed.add_field(name="Team Selection", value=queue.teamSelection, inline=False)
        embed.add_field(name="Channels", value="{}\n".format(", ".join([channel.mention for channel in queue.channels])), inline=False)
        embed.add_field(name="Games Played", value="{}\n".format(queue.gamesPlayed), inline=False)
        embed.add_field(name="Unique Players All-Time", value="{}\n".format(len(queue.players)), inline=False)
        embed.add_field(name="Point Breakdown", value="**Per Series Played:** {0}\n**Per Series Win:** {1}"
            .format(queue.points[Strings.PP_PLAY_KEY], queue.points[Strings.PP_WIN_KEY]), inline=False)
        return embed

    def embed_queue_players(self, queue: SixMansQueue):
        player_list = self.format_player_list(queue)
        embed = discord.Embed(title="{0} {1} Mans Queue".format(queue.name, queue.maxSize), color=discord.Colour.blue())
        embed.add_field(name="Players in Queue ({}/{})".format(len(queue.queue.queue), queue.maxSize), value=player_list, inline=False)
        return embed

    def embed_active_games(self, guild, queueGames: Dict[int, List[Game]]):
        embed = discord.Embed(title="{0} Mans Active Games".format(self.queueMaxSize[guild]), color=discord.Colour.blue())
        for queueId in queueGames.keys():
            games = queueGames[queueId]
            queueName = next(queue.name for queue in self.queues[guild] if queue.id == queueId)
            embed.add_field(name="{}:".format(queueName), value="{}".format("\n".join(["{0}\n{1}".format(str(game.id), ", ".join([player.mention for player in game.players])) for game in games])), inline=False)
        return embed

    async def embed_leaderboard(self, ctx: Context, sorted_players, queue_name, games_played, lb_format):
        embed = discord.Embed(title="{0} {1} Mans {2} Leaderboard".format(queue_name, self.queueMaxSize[ctx.guild], lb_format), color=discord.Colour.blue())
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

    def embed_rank(self, player, sorted_players, queue_name, queue_max_size, rank_format):
        try:
            num_players = len(sorted_players)
            points_index = [y[0] for y in sorted_players].index("{0}".format(player.id))
            player_info = sorted_players[points_index][1]
            points, wins, games_played = player_info[Strings.PLAYER_POINTS_KEY], player_info[Strings.PLAYER_WINS_KEY], player_info[Strings.PLAYER_GP_KEY]
            wins_index = [y[0] for y in sorted(sorted_players, key=lambda x: x[1][Strings.PLAYER_WINS_KEY], reverse=True)].index("{0}".format(player.id))
            games_played_index = [y[0] for y in sorted(sorted_players, key=lambda x: x[1][Strings.PLAYER_GP_KEY], reverse=True)].index("{0}".format(player.id))
            embed = discord.Embed(title="{0} {1} {2} Mans {3} Rank".format(player.display_name, queue_name, queue_max_size, rank_format), color=discord.Colour.blue())
            embed.set_thumbnail(url=player.avatar_url)
            embed.add_field(name="Points:", value="**Value:** {2} | **Rank:** {0}/{1}".format(points_index + 1, num_players, points), inline=True)
            embed.add_field(name="Wins:", value="**Value:** {2} | **Rank:** {0}/{1}".format(wins_index + 1, num_players, wins), inline=True)
            embed.add_field(name="Games Played:", value="**Value:** {2} | **Rank:** {0}/{1}".format(games_played_index + 1, num_players, games_played), inline=True)
        except:
            embed = discord.Embed(title="{0} {1} {2} Mans {3} Rank".format(player.display_name, queue_name, queue_max_size, rank_format), color=discord.Colour.red(),
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
    async def _pre_load_data(self):
        await self.bot.wait_until_ready()
        self.queues = {}
        self.games = {}

        for guild in self.bot.guilds:
            self.queues[guild] = []
            self.games[guild] = []

            # Preload General Data
            self.queueMaxSize[guild] = await self._get_queue_max_size(guild)
            self.player_timeout_time[guild] = await self._player_timeout(guild) ## if not DEBUG else PLAYER_TIMEOUT_TIME

            # Pre-load Queues
            queues = await self._queues(guild)
            default_team_selection = await self._team_selection(guild)
            default_queue_size = self.queueMaxSize[guild]
            default_category = await self._category(guild)
            default_lobby_vc = await self._get_q_lobby_vc(guild)
            for key, value in queues.items():
                queue_channels = [guild.get_channel(x) for x in value["Channels"]]
                queue_name = value["Name"]
                team_selection = value.setdefault("TeamSelection", default_team_selection)
                queue_size = value.setdefault("MaxSize", default_queue_size)
                if default_category:
                    category = guild.get_channel(value.setdefault("Category", default_category.id))
                elif "Category" in value and value["Category"]:
                    category = value["Category"]
                else:
                    category = None
                
                if default_lobby_vc:
                    lobby_vc = guild.get_channel(value.setdefault("Category", default_lobby_vc.id))
                elif "Category" in value and value["Category"]:
                    lobby_vc = value["Category"]
                else:
                    lobby_vc = None
                six_mans_queue = SixMansQueue(queue_name, guild, queue_channels, 
                    value["Points"], 
                    value["Players"], 
                    value["GamesPlayed"], 
                    queue_size, 
                    teamSelection=team_selection,
                    category=category,
                    lobby_vc=lobby_vc
                )
                
                six_mans_queue.id = int(key)
                self.queues[guild].append(six_mans_queue)
            
            # Pre-load Games
            games = await self._games(guild)
            game_list = []
            for key, value in games.items():
                players = [guild.get_member(x) for x in value["Players"]]
                text_channel = guild.get_channel(value["TextChannel"])
                voice_channels = [guild.get_channel(x) for x in value["VoiceChannels"]]
                queueId = value["QueueId"]

                queue = None
                for q in self.queues[guild]:
                    if q.id == queueId:
                        queue = q
                        
                game = Game(players, queue, text_channel=text_channel, voice_channels=voice_channels, observers=self.observers)
                game.id = int(key)
                game.captains = [guild.get_member(x) for x in value["Captains"]]
                game.blue = set([guild.get_member(x) for x in value["Blue"]])
                game.orange = set([guild.get_member(x) for x in value["Orange"]])
                game.roomName = value["RoomName"]
                game.roomPass = value["RoomPass"]
                game.use_reactions = value["UseReactions"]
                try:
                    game.info_message = await game.textChannel.fetch_message(value["InfoMessage"])
                    game.teamSelection = value["TeamSelection"]
                except:
                    game.teamSelection = game.queue.teamSelection
                    await game.process_team_selection_method()
                game.scoreReported = value["ScoreReported"]
                game_list.append(game)
            
            self.games[guild] = game_list

    async def _clear_all_data(self, guild: discord.Guild):
        await self._save_games(guild, [])
        await self._save_queues(guild, [])
        await self._save_scores(guild, [])
        await self._save_games_played(guild, 0)
        await self._save_players(guild, {})
        await self._save_category(guild, None)
        await self._save_q_lobby_vc(guild, None)
        await self._save_queue_max_size(guild, 6)
        await self._save_player_timeout(guild, PLAYER_TIMEOUT_TIME)
        await self._save_helper_role(guild, None)
        await self._save_team_selection(guild, Strings.RANDOM_TS)
        await self._save_react_to_vote(guild, True)
        await self._save_automove(guild, False)

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

    async def _player_timeout(self, guild: discord.Guild):
        return await self.config.guild(guild).PlayerTimeout()
    
    async def _save_player_timeout(self, guild: discord.Guild, time_seconds: int):
        await self.config.guild(guild).PlayerTimeout.set(time_seconds)

    async def _players(self, guild: discord.Guild):
        return await self.config.guild(guild).Players()

    async def _save_players(self, guild: discord.Guild, players):
        await self.config.guild(guild).Players.set(players)

    async def _get_automove(self, guild: discord.Guild):
        return await self.config.guild(guild).AutoMove()

    async def _save_automove(self, guild: discord.Guild, automove: bool):
        await self.config.guild(guild).AutoMove.set(automove)

    async def _is_react_to_vote(self, guild: discord.Guild):
        return await self.config.guild(guild).ReactToVote()

    async def _save_react_to_vote(self, guild: discord.Guild, automove: bool):
        await self.config.guild(guild).ReactToVote.set(automove)

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

    async def _get_queue_max_size(self, guild: discord.Guild):
        return await self.config.guild(guild).DefaultQueueMaxSize()
    
    async def _save_queue_max_size(self, guild: discord.Guild, max_size: int):
        await self.config.guild(guild).DefaultQueueMaxSize.set(max_size)
        self.queueMaxSize[guild] = int

    async def _helper_role(self, guild: discord.Guild):
        return guild.get_role(await self.config.guild(guild).HelperRole())

    async def _save_helper_role(self, guild: discord.Guild, helper_role):
        await self.config.guild(guild).HelperRole.set(helper_role)

    async def _save_team_selection(self, guild: discord.Guild, team_selection):
        await self.config.guild(guild).DefaultTeamSelection.set(team_selection)
    
    async def _team_selection(self, guild: discord.Guild):
        return await self.config.guild(guild).DefaultTeamSelection()

#endregion
