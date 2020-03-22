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
from redbot.core.utils.menus import start_adding_reactions, menu, DEFAULT_CONTROLS

team_size = 3
minimum_game_time = 600 #Seconds (10 Minutes)
verify_timeout = 15
start_game_verify_timeout = 60
k_factor = 50
default_elo = 1500

defaults = {"CategoryChannel": None, "TextChannel": None, "HelperRole": None, "Games": {}, "GamesPlayed": 0, "Teams": {}, "Scores": []}

class Ladder(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567880, force_registration=True)
        self.config.register_guild(**defaults)
        self.games = []
        self.teams = []

    @commands.guild_only()
    @commands.command(aliases=["rlt"])
    async def registerLadderTeam(self, ctx, team_name, captain: discord.Member, *players: discord.Member):
        """Creates a team with a given name and players. The team will need to be approved first before it can actually begin participating.
        The first player listed when using the command will be made captain of the team. **Team names will need to be in quotes.**"""
        await self.load_teams(ctx)
        if any(team.name.lower() == team_name.lower() for team in self.teams):
            await ctx.send(":x: {} is already the name of a team".format(team_name))
            return

        player_list = list(players)
        if captain not in player_list:
            player_list.append(captain)
        if len(player_list) != team_size:
            await ctx.send(":x: Teams must be {} players exactly".format(team_size))
            return
        if ctx.author not in player_list:
            await ctx.send(":x: You can only register a team that you're a player on")
            return
        
        team = Team(team_name, captain, player_list, 0, 0, default_elo, False)
        self.teams.append(team)
        await self._save_teams(ctx, self.teams)
        await ctx.send("Done\nYour team will need to be approved first before you can participate in the event. You'll get a dm when that has occurred.")

    @commands.guild_only()
    @commands.command(aliases=["glt"])
    async def getLadderTeams(self, ctx):
        """Gets info for all the ladder teams that have been approved already."""
        await self.load_teams(ctx)
        approvedTeams = [team for team in self.teams if team.approved]
        if not approvedTeams:
            ctx.send("There are no approved teams at this time")
            return
        embeds = []
        for team in approvedTeams:
            embed = self.embed_team_info(team)
            embeds.append(embed)
        await ctx.send("There are currently {} ladder teams:".format(len(approvedTeams)))
        await menu(ctx, embeds, DEFAULT_CONTROLS)

    @commands.guild_only()
    @commands.command(aliases=["gult"])
    async def getUnapprovedLadderTeams(self, ctx):
        """Gets a list of the registered teams that haven't been approved to participate yet. This should help when determining whether to approve a team or not."""
        if not await self.has_perms(ctx):
            return
        await self.load_teams(ctx)
        unapprovedTeams = [team for team in self.teams if not team.approved]
        if not unapprovedTeams:
            ctx.send("There are no unapproved teams at this time")
            return
        embeds = []
        for team in unapprovedTeams:
            embed = self.embed_team_player_info(team)
            embeds.append(embed)
        await ctx.send("There are currently {} unapproved teams:".format(len(unapprovedTeams)))
        await menu(ctx, embeds, DEFAULT_CONTROLS)

    @commands.guild_only()
    @commands.command(aliases=["alt"])
    async def approveLadderTeam(self, ctx, team_name, elo_rating: int = default_elo):
        """Approves a team to participate in the event. Make sure that they fit under whatever guidelines we set before approving them.
        The players will get a dm saying their team has been approved."""
        if not await self.has_perms(ctx):
            return
        try:
            team = next(team for team in self.teams if team.name.lower() == team_name.lower())
        except:
            await ctx.send(":x: No team found with name {}".format(team_name))
            return
        if team.approved:
            await ctx.send(":x: {} has already been approved".format(team_name))
            return
        team.elo_rating = elo_rating
        team.approved = True
        await self._save_teams(ctx, self.teams)
        for player in team.players:
            try:
                await player.send(":white_check_mark: Your ladder team, {0}, has been approved to participate in the ladder event within {1}".format(team.name, ctx.guild.name))
            except:
                pass
        await ctx.send("Done\nDM was sent to the players of that team.")

    @commands.guild_only()
    @commands.command(aliases=["rjlt"])
    async def rejectLadderTeam(self, ctx, team_name, *reason):
        """Rejects a team and prevents them from participating in the event. This cannot be undone, but the team can try and register again.
        There's an optional parameter for including a reason why they were rejected. The players will get a dm saying their team was rejected along with the reason if given."""
        if not await self.has_perms(ctx):
            return
        try:
            team = next(team for team in self.teams if team.name.lower() == team_name.lower())
        except:
            await ctx.send(":x: No team found with name {}".format(team_name))
            return
        if team.approved:
            await ctx.send(":x: {} has already been approved".format(team_name))
            return
        self.teams.remove(team)
        await self._save_teams(ctx, self.teams)
        for player in team.players:
            try:
                if len(reason) > 0:
                    await player.send(":x: Your ladder team, {0}, has been rejected and will not be allowed to participate in the ladder event within {1}. "
                        "Reason for rejection: `{2}`. To register a new team you can use the `{3}rlt` command again".format(team.name, ctx.guild.name, reason, ctx.prefix))
                else:
                    await player.send(":x: Your ladder team, {0}, has been rejected and will not be allowed to participate in the ladder event within {1}. "
                        "To register a new team you can use the `{2}rlt` command again".format(team.name, ctx.guild.name, ctx.prefix))
            except:
                pass
        await ctx.send("Done\nDM was sent to the players of that team.")

    @commands.guild_only()
    @commands.command(aliases=["slg"])
    async def startLadderGame(self, ctx, team_1_name, team_2_name):
        """Attempts to start a ladder game between the two teams. You'll need to be a player on one of the teams to use this
        command and the other team's captain will need to agree to start the game as well."""
        await self.load_teams(ctx)
        try:
            team_1 = next(team for team in self.teams if team.name.lower() == team_1_name.lower())
            team_2 = next(team for team in self.teams if team.name.lower() == team_2_name.lower())
        except:
            await ctx.send(":x: One of the two team names didn't match a team")
            return
        if team_1 == team_2:
            await ctx.send(":x: The two teams used in the command are the same")
            return
        if not team_1.approved or not team_2.approved:
            await ctx.send(":x: One of the two teams has not been approved to participate yet")
            return
        if ctx.author not in team_1.players and ctx.author not in team_2.players:
            await ctx.send(":x: You can't start a game between two teams that you're not a player on")
            return
        
        if await self.verify_start_game(ctx, team_1, team_2, self.get_opposing_captain_by_teams(ctx, team_1, team_2)):
            game = await self.create_game(ctx, team_1, team_2)
            await self.send_game_info(ctx, game)
            self.games.append(game)
            await self._save_games(ctx, self.games)
            await ctx.send("Done")

    @commands.guild_only()
    @commands.command(aliases=["fslg"])
    @checks.admin_or_permissions(manage_guild=True)
    async def forceStartLadderGame(self, ctx, team_1_name, team_2_name):
        """Primarily for testing. Forces a new game between two teams."""
        await self.load_teams(ctx)
        try:
            team_1 = next(team for team in self.teams if team.name.lower() == team_1_name.lower())
            team_2 = next(team for team in self.teams if team.name.lower() == team_2_name.lower())
        except:
            await ctx.send(":x: One of the two team names didn't match a team")
            return
        if team_1 == team_2:
            await ctx.send(":x: The two teams used in the command are the same")
            return
        if not team_1.approved or not team_2.approved:
            await ctx.send(":x: One of the two teams has not been approved to participate yet")
            return
        if ctx.author not in team_1.players and ctx.author not in team_2.players:
            await ctx.send(":x: You can't start a game between two teams that you're not a player on")
            return

        game = await self.create_game(ctx, team_1, team_2)
        await self.send_game_info(ctx, game)
        self.games.append(game)
        await self._save_games(ctx, self.games)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command(aliases=["clg"])
    async def cancelLadderGame(self, ctx):
        """Cancel the current ladder game. Can only be used in a ladder game channel.
        The game will end with no wins given to either team. The teams will then be allowed to start a new game."""
        await self.load_teams(ctx)
        await self.load_games(ctx)
        try:
            game = next(game for game in self.games if game.textChannel == ctx.channel)
        except:
            await ctx.send(":x: This command can only be used in a ladder game channel.")
            return

        opposing_captain = self.get_opposing_captain(ctx, game)
        if opposing_captain is None:
            await ctx.send(":x: Only players on one of the two teams can cancel the game.")
            return

        msg = await ctx.send("{0} Please verify that both teams want to cancel the game. You have {1} seconds to verify".format(opposing_captain.mention, verify_timeout))
        start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)

        pred = ReactionPredicate.yes_or_no(msg, opposing_captain)
        try:
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=verify_timeout)
            if pred.result is True:
                await ctx.send("Done. Feel free to start a new game.\n**This channel will be deleted in 30 seconds**")
                await self.remove_game(ctx, game)
            else:
                await ctx.send(":x: Cancel not verified. To cancel the game you will need to use the `{0}clg` command again.".format(ctx.prefix))
        except asyncio.TimeoutError:
            await ctx.send(":x: Cancel not verified in time. To cancel the game you will need to use the `{0}clg` command again."
                "\n**If one of the captains is afk, have someone from that team use the command.**".format(ctx.prefix))

    @commands.guild_only()
    @commands.command(aliases=["fclg"])
    async def forceCancelLadderGame(self, ctx):
        """Cancel the current ladder game. Can only be used in a ladder game channel.
        The game will end with no wins given to either team. The teams will then be allowed to start a new game."""
        if not await self.has_perms(ctx):
            return

        await self.load_teams(ctx)
        await self.load_games(ctx)
        try:
            game = next(game for game in self.games if game.textChannel == ctx.channel)
        except:
            await ctx.send(":x: This command can only be used in a ladder game channel.")
            return

        msg = await ctx.send("{0} Please verify that you want to cancel this game.".format(ctx.author.mention))
        start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)

        game.scoreReported = True
        pred = ReactionPredicate.yes_or_no(msg, ctx.author)
        try:
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=verify_timeout)
            if pred.result is True:
                await ctx.send("Done. Feel free to start a new game.\n**This channel will be deleted in 30 seconds**")
                await self.remove_game(ctx, game)
            else:
                await ctx.send(":x: Cancel not verified. To cancel the game you will need to use the `{0}clg` command again.".format(ctx.prefix))
        except asyncio.TimeoutError:
            await ctx.send(":x: Cancel not verified in time. To cancel the game you will need to use the `{0}clg` command again.".format(ctx.prefix))

    @commands.guild_only()
    @commands.command(aliases=["lr"])
    async def ladderResult(self, ctx, blue_team_wins: int, orange_team_wins: int):
        """Submits the result of the ladder game. Should be used in the text channel corresponding to the game.
        Both teams need to agree on the result before it is finalized."""
        await self.load_teams(ctx)
        await self.load_games(ctx)
        try:
            game = next(game for game in self.games if game.textChannel == ctx.channel)
        except:
            await ctx.send(":x: This command can only be used in a ladder game channel.")
            return
        if game.scoreReported == True:
            await ctx.send(":x: Someone has already reported the results or is waiting for verification")
            return
        game_time = ctx.message.created_at - ctx.channel.created_at
        if game_time.seconds < minimum_game_time:
            await ctx.send(":x: You can't report a game outcome until at least **10 minutes** have passed since the game was created."
                "\nCurrent time that's passed = **{0} minute(s)**".format(game_time.seconds // 60))
            return
        opposing_captain = self.get_opposing_captain(ctx, game)
        if opposing_captain is None:
            await ctx.send(":x: Only players on one of the two teams can report the result.")
            return

        if await self.verify_game_results(ctx, game, blue_team_wins, orange_team_wins, opposing_captain):
            await self.finish_game(ctx, game, blue_team_wins, orange_team_wins)
            await ctx.send("Done. Thanks for playing!\n**This channel and the team voice channels will be deleted in 30 seconds**")
            await self.remove_game(ctx, game)

    @commands.guild_only()
    @commands.command(aliases=["flr"])
    async def forceLadderResult(self, ctx, blue_team_wins: int, orange_team_wins: int):
        """Overrides the verification process for submitting the result of a game in the case that the two teams can't submit it themselves."""
        if not await self.has_perms(ctx):
            return

        await self.load_teams(ctx)
        await self.load_games(ctx)
        try:
            game = next(game for game in self.games if game.textChannel == ctx.channel)
        except:
            await ctx.send(":x: This command can only be used in a ladder game channel.")
            return

        if await self.verify_game_results(ctx, game, blue_team_wins, orange_team_wins, ctx.author):
            await self.finish_game(ctx, game, blue_team_wins, orange_team_wins)
            await ctx.send("Done. Thanks for playing!\n**This channel and the team voice channels will be deleted in 30 seconds**")
            await self.remove_game(ctx, game)

    @commands.guild_only()
    @commands.command(aliases=["llb"])
    async def ladderLeaderboard(self, ctx):
        """Shows the top ten teams in terms of current Elo rating"""
        await self.load_teams(ctx)
        approvedTeams = [team for team in self.teams if team.approved]
        if not approvedTeams:
            ctx.send("There are no approved teams at this time")
            return
        approvedTeams.sort(key=lambda team: team.elo_rating, reverse=True)
        await ctx.send(embed=self.embed_leaderboard(ctx, approvedTeams, await self._games_played(ctx)))

    @commands.guild_only()
    @commands.command(aliases=["glti"])
    async def getLadderTeamInfo(self, ctx, team_name):
        """"Gets all the info corresponding to a ladder team. **Team names will need to be in quotes.**
        Shows the captain, players, team record, and Elo rating."""
        await self.load_teams(ctx)
        try:
            team = next(team for team in self.teams if team.name.lower() == team_name.lower())
            await ctx.send(embed=self.embed_team_info(team))
        except:
            await ctx.send(":x: There's no team with the name: {}".format(team_name))

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setLadderTextChannel(self, ctx, text_channel: discord.TextChannel):
        """Sets the ladder text channel where general ladder info will be sent"""
        await self._save_text_channel(ctx, text_channel.id)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def getLadderTextChannel(self, ctx):
        """Gets the ladder text channel"""
        try:
            await ctx.send("Ladder text channel set to: {0}".format((await self._text_channel(ctx)).mention))
        except:
            await ctx.send(":x: Ladder text channel not set")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def unsetLadderTextChannel(self, ctx):
        """Unsets the ladder text channel"""
        await self._save_text_channel(ctx, None)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setLadderCategory(self, ctx, category_channel: discord.CategoryChannel):
        """Sets the ladder category channel where all ladder channels will be created under"""
        await self._save_category(ctx, category_channel.id)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def getLadderCategory(self, ctx):
        """Gets the channel currently assigned as the ladder category channel"""
        try:
            await ctx.send("Ladder category channel set to: {0}".format((await self._category(ctx)).mention))
        except:
            await ctx.send(":x: Ladder category channel not set")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def unsetLadderCategory(self, ctx):
        """Unsets the ladder category channel. Ladder channels will not be created if this is not set"""
        await self._save_category(ctx, None)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setLadderHelperRole(self, ctx, helper_role: discord.Role):
        """Sets the ladder helper role. Anyone with this role will be able to see all the ladder game channels that are created"""
        await self._save_helper_role(ctx, helper_role.id)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def getLadderHelperRole(self, ctx):
        """Gets the ladder helper role"""
        try:
            await ctx.send("Ladder helper role set to: {0}".format((await self._helper_role(ctx)).name))
        except:
            await ctx.send(":x: ladder helper role not set")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def unsetLadderHelperRole(self, ctx):
        """Unsets the ladder helper role"""
        await self._save_helper_role(ctx, None)
        await ctx.send("Done")

    async def has_perms(self, ctx):
        helper_role = await self._helper_role(ctx)
        if ctx.author.guild_permissions.administrator:
            return True
        elif helper_role and helper_role in ctx.author.roles:
            return True

    async def create_game(self, ctx, team_1, team_2):
        text_channel, voice_channels = await self.create_game_channels(ctx, team_1, team_2)
        players = list(team_1.players) + list(team_2.players)
        for player in players:
            await text_channel.set_permissions(player, read_messages=True)
        return Game(team_1, team_2, text_channel, voice_channels)

    async def create_game_channels(self, ctx, team_1, team_2):
        guild = ctx.message.guild
        helper_role = await self._helper_role(ctx)
        if helper_role:
            text_overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                helper_role: discord.PermissionOverwrite(read_messages=True, manage_channels=True)
            }
            voice_overwrites = {
                guild.default_role: discord.PermissionOverwrite(connect=False),
                helper_role: discord.PermissionOverwrite(connect=True, manage_channels=True)
            }
        else:
            text_overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False)
            }
            voice_overwrites = {
                guild.default_role: discord.PermissionOverwrite(connect=False)
            }
        
        text_channel = await guild.create_text_channel("{0} vs {1} Ladder Game".format(team_1.name, team_2.name), overwrites= text_overwrites,
            category= await self._category(ctx))
        voice_channels = [
            await guild.create_voice_channel("{}".format(team_1.name), overwrites= voice_overwrites, category= await self._category(ctx)),
            await guild.create_voice_channel("{}".format(team_2.name), overwrites= voice_overwrites, category= await self._category(ctx))
        ]
        return text_channel, voice_channels

    async def verify_start_game(self, ctx, team_1, team_2, opposing_captain: discord.Member):
        msg = await ctx.send("{0} Please verify that you want to start the game between these two teams:".format(opposing_captain.mention), embed=self.embed_team_comparison(team_1, team_2))
        start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)
        pred = ReactionPredicate.yes_or_no(msg, opposing_captain)
        try:
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=start_game_verify_timeout)
            if pred.result is True:
                return True
            else:
                await ctx.send(":x: Ladder game between **{0}** and **{1}** not started.\nTo try and start a new game again use the `{2}slg` command.".format(team_1.name, team_2.name, ctx.prefix))
                return False
        except asyncio.TimeoutError:
            await ctx.send(":x: Ladder game between **{0}** and **{1}** not verified in time.\nTo try and start a new game again use the `{2}slg` command.".format(team_1.name, team_2.name, ctx.prefix))
            return False

    async def verify_game_results(self, ctx, game, blue_team_wins, orange_team_wins, verifier: discord.Member):
        msg = await ctx.send("{0} Please verify the results:\n**{1}** {2} - {3} **{4}**".format(verifier.mention, game.blue.name,
            blue_team_wins, orange_team_wins, game.orange.name))
        start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)
        game.scoreReported = True
        pred = ReactionPredicate.yes_or_no(msg, verifier)
        try:
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=verify_timeout)
            if pred.result is True:
                return True
            else:
                game.scoreReported = False
                await ctx.send(":x: Ladder game result not verified. To report the result you will need to use the `{0}lr` command again.".format(ctx.prefix))
                return False
        except asyncio.TimeoutError:
            game.scoreReported = False
            await ctx.send(":x: Ladder game result not verified in time. To report the result you will need to use the `{0}lr` command again.\n"
                "**If one of the captains is afk, have someone from that team use the command.**".format(ctx.prefix))
            return False

    async def finish_game(self, ctx, game, blue_team_wins, orange_team_wins):
        blue_team = game.blue
        orange_team = game.orange
        blue_team_new_elo, orange_team_new_elo = self.update_elo(blue_team.elo_rating, orange_team.elo_rating, blue_team_wins / (blue_team_wins + orange_team_wins))
        await ctx.send(embed=self.embed_game_results(blue_team, blue_team_wins, orange_team_wins, orange_team, blue_team_new_elo, orange_team_new_elo))
        self.update_team_info(blue_team, blue_team_wins, orange_team_wins, blue_team_new_elo)
        self.update_team_info(orange_team, orange_team_wins, blue_team_wins, orange_team_new_elo)
        await self._save_teams(ctx, self.teams)
        await self._save_games_played(ctx, (await self._games_played(ctx)) + blue_team_wins + orange_team_wins)

    async def remove_game(self, ctx, game):
        self.games.remove(game)
        await self._save_games(ctx, self.games)
        await asyncio.sleep(30)
        await ctx.channel.delete()
        for vc in game.voiceChannels:
            await vc.delete()

    def get_opposing_captain(self, ctx, game):
        return self.get_opposing_captain_by_teams(ctx, game.blue, game.orange)

    def get_opposing_captain_by_teams(self, ctx, team_1, team_2):
        opposing_captain = None
        if ctx.author in team_1.players:
            opposing_captain = team_2.captain
        elif ctx.author in team_2.players:
            opposing_captain = team_1.captain
        return opposing_captain

    def update_team_info(self, team, wins, losses, elo_rating):
        team.wins += wins
        team.losses += losses
        team.elo_rating = elo_rating

    def update_elo(self, team_1_elo, team_2_elo, result):
        """Calculates and returns the new Elo ratings for the two teams based on their match results and the K-factor.
        Result param should be a decimal between 0 and 1 relating to the match results for team 1, i.e. a result of 1 
        means team 1 won all the games in the match, a result of .25 means team 1 won 25% of the games in the match."""
        elo_dif = team_1_elo - team_2_elo
        exponent = -1 * (elo_dif / 100)
        expectation = 1 / (1 + pow(10, exponent))
        team_1_new_elo = round(team_1_elo + (k_factor * (result - expectation)))
        team_2_new_elo = round(team_2_elo + (k_factor * ((1 - result) - (1 - expectation))))
        return team_1_new_elo, team_2_new_elo

    def embed_team_comparison(self, team_1, team_2):
        embed = discord.Embed(title="{0} vs. {1} Team Comparison".format(team_1.name, team_2.name), color=discord.Colour.blue())
        embed.add_field(name="Players", value="**{0}**: {1}\n**{2}**: {3}\n".format(team_1.name, ", ".join([player.mention for player in team_1.players]),
            team_2.name, ", ".join([player.mention for player in team_2.players])), inline=False)
        embed.add_field(name="Records", value="**{0}**: {1} - {2}\n**{3}**: {4} - {5}\n".format(team_1.name, team_1.wins, team_1.losses, team_2.name, team_2.wins, team_2.losses), inline=False)
        embed.add_field(name="Elo Ratings", value="**{0}**: {1}\n**{2}**: {3}\n".format(team_1.name, team_1.elo_rating, team_2.name, team_2.elo_rating), inline=False)
        return embed

    async def send_game_info(self, ctx, game):
        helper_role = await self._helper_role(ctx)
        await game.textChannel.send("{}\n".format(", ".join([player.mention for player in game.players])))
        embed = discord.Embed(title="{0} vs. {1} Ladder Game Info".format(game.blue.name, game.orange.name), color=discord.Colour.blue())
        embed.add_field(name="Blue Team", value="**{0}**: {1}\n".format(game.blue.name, ", ".join([player.mention for player in game.blue.players])), inline=False)
        embed.add_field(name="Orange Team", value="**{0}**: {1}\n".format(game.orange.name, ", ".join([player.mention for player in game.orange.players])), inline=False)
        embed.add_field(name="Captains", value="**Blue:** {0}\n**Orange:** {1}".format(game.blue.captain.mention, game.orange.captain.mention), inline=False)
        embed.add_field(name="Lobby Info", value="**Name:** {0}\n**Password:** {1}".format(game.roomName, game.roomPass), inline=False)
        embed.add_field(name="Additional Info", value="Feel free to play whatever type of series you want, whether a bo3, bo5, or any other.\n\n"
            "When you are done playing with the current teams please report the results using the command `{0}lr [blue_team_wins] [orange_team_wins]` where both "
            "the `blue_team_wins` and `orange_team_wins` parameters are the number of wins each team had. Both teams will need to verify the results.\n\nIf you wish to cancel "
            "the game you can use the `{0}clg` command. Both teams will need to verify that they wish to cancel the game.".format(ctx.prefix), inline=False)
        help_message = "If you think the bot isn't working correctly or have suggestions to improve it, please contact adammast."
        if helper_role:
            help_message = "If you need any help or have questions please contact someone with the {0} role. ".format(helper_role.mention) + help_message
        embed.add_field(name="Help", value=help_message, inline=False)
        await game.textChannel.send(embed=embed)

    def embed_game_results(self, team_1, team_1_wins: int, team_2_wins: int, team_2, team_1_new_elo, team_2_new_elo):
        embed = discord.Embed(title="{0} vs. {1}".format(team_1.name, team_2.name), color=discord.Colour.blue())
        embed.add_field(name="Players", value="**{0}**: {1}\n**{2}**: {3}\n".format(team_1.name, ", ".join([player.mention for player in team_1.players]),
            team_2.name, ", ".join([player.mention for player in team_2.players])), inline=False)
        embed.add_field(name="Result", value="**{0}** {1} - {2} **{3}**\n".format(team_1.name, team_1_wins, team_2_wins, team_2.name), inline=False)
        embed.add_field(name="Updated Elo Rating", value="**{0}** = {1} ({2})\n**{3}** = {4} ({5})\n".format(team_1.name, team_1_new_elo, team_1_new_elo - team_1.elo_rating,
            team_2.name, team_2_new_elo, team_2_new_elo - team_2.elo_rating), inline=False)
        return embed

    def embed_team_player_info(self, team):
        embed = discord.Embed(title="{0}".format(team.name), color=discord.Colour.blue())
        embed.add_field(name="Captain", value="{}\n".format(team.captain.mention), inline=False)
        embed.add_field(name="Players", value="{}\n".format(", ".join([player.mention for player in team.players])), inline=False)
        return embed

    def embed_team_info(self, team):
        embed = self.embed_team_player_info(team)
        embed.add_field(name="Games Played", value="{}\n".format(team.wins + team.losses), inline=False)
        embed.add_field(name="Record", value="{0} - {1}\n".format(team.wins, team.losses), inline=False)
        embed.add_field(name="Elo Rating", value="{}\n".format(team.elo_rating), inline=False)
        return embed

    def embed_leaderboard(self, ctx, sorted_teams, games_played):
        embed = discord.Embed(title="{0} Ladder Leaderboard".format(ctx.guild.name), color=discord.Colour.blue())
        embed.add_field(name="Total Games Played", value="{}\n".format(games_played), inline=True)
        
        index = 1
        message = ""
        for team in sorted_teams:
            message += "`{0}` __**{1}:**__ **Elo Rating:** {2}  **Record:** {3} - {4}  **Games Played:** {5}\n".format(index, team.name, team.elo_rating, 
                team.wins, team.losses, team.wins + team.losses)
            index += 1
            if index > 10:
                break

        embed.add_field(name="Highest Elo Rating", value=message, inline=False)
        return embed

    async def load_teams(self, ctx, force_load = False):
        if self.teams is None or self.teams == [] or force_load:
            teams = await self._teams(ctx)
            team_list = []
            for key, value in teams.items():
                name = value["Name"]
                captain = ctx.guild.get_member(value["Captain"])
                players = [ctx.guild.get_member(x) for x in value["Players"]]
                wins = value["Wins"]
                losses = value["Losses"]
                elo_rating = value["EloRating"]
                approved = value["Approved"]
                team = Team(name, captain, players, wins, losses, elo_rating, approved)
                team.id = int(key)
                team_list.append(team)

            self.teams = team_list

    async def _teams(self, ctx):
        return await self.config.guild(ctx.guild).Teams()

    async  def _save_teams(self, ctx, teams):
        team_dict = {}
        for team in teams:
            team_dict[team.id] = team._to_dict()
        await self.config.guild(ctx.guild).Teams.set(team_dict)

    async def load_games(self, ctx, force_load = False):
        if self.games is None or self.games == [] or force_load:
            self.load_teams(ctx, force_load)
            games = await self._games(ctx)
            game_list = []
            for key, value in games.items():
                text_channel = ctx.guild.get_channel(value["TextChannel"])
                voice_channels = [ctx.guild.get_channel(x) for x in value["VoiceChannels"]]
                blue_team_id = value["Blue"]
                orange_team_id = value["Orange"]
                blue_team = next(x for x in self.teams if x.id == blue_team_id)
                orange_team = next(x for x in self.teams if x.id == orange_team_id)
                game = Game(blue_team, orange_team, text_channel, voice_channels)
                game.id = int(key)
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

    async def _scores(self, ctx):
        return await self.config.guild(ctx.guild).Scores()

    async def _save_scores(self, ctx, scores):
        await self.config.guild(ctx.guild).Scores.set(scores)

    async def _games_played(self, ctx):
        return await self.config.guild(ctx.guild).GamesPlayed()

    async def _save_games_played(self, ctx, games_played):
        await self.config.guild(ctx.guild).GamesPlayed.set(games_played)

    async def _category(self, ctx):
        return ctx.guild.get_channel(await self.config.guild(ctx.guild).CategoryChannel())

    async def _save_category(self, ctx, category):
        await self.config.guild(ctx.guild).CategoryChannel.set(category)

    async def _text_channel(self, ctx):
        return ctx.guild.get_channel(await self.config.guild(ctx.guild).TextChannel())

    async def _save_text_channel(self, ctx, text_channel):
        await self.config.guild(ctx.guild).TextChannel.set(text_channel)

    async def _helper_role(self, ctx):
        return ctx.guild.get_role(await self.config.guild(ctx.guild).HelperRole())

    async def _save_helper_role(self, ctx, helper_role):
        await self.config.guild(ctx.guild).HelperRole.set(helper_role)

class Team:
    def __init__(self, name, captain, players, wins, losses, elo_rating, approved):
        self.id = uuid.uuid4().int
        self.name = name
        self.captain = captain
        self.players = set(players)
        self.wins = wins
        self.losses = losses
        self.elo_rating = elo_rating
        self.approved = approved

    def _to_dict(self):
        return {
            "Name": self.name,
            "Captain": self.captain.id,
            "Players": [x.id for x in self.players],
            "Wins": self.wins,
            "Losses": self.losses,
            "EloRating": self.elo_rating,
            "Approved": self.approved
        }

class Game:
    def __init__(self, blue_team: Team, orange_team: Team, text_channel, voice_channels):
        self.id = uuid.uuid4().int
        self.captains = [blue_team.captain, orange_team.captain]
        self.players = blue_team.players.union(orange_team.players)
        self.blue = blue_team
        self.orange = orange_team
        self.roomName = self._generate_name_pass()
        self.roomPass = self._generate_name_pass()
        self.textChannel = text_channel
        self.voiceChannels = voice_channels #List of voice channels: [Blue, Orange]
        self.scoreReported = False

    def _to_dict(self):
        return {
            "Blue": self.blue.id,
            "Orange": self.orange.id,
            "RoomName": self.roomName,
            "RoomPass": self.roomPass,
            "TextChannel": self.textChannel.id,
            "VoiceChannels": [x.id for x in self.voiceChannels],
            "ScoreReported": self.scoreReported
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