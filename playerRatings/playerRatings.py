import discord
import asyncio
import uuid
import ast

from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions, menu, DEFAULT_CONTROLS

k_factor = 30

defaults = {"Players": {}, "Results": []}

class PlayerRatings(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567870, force_registration=True)
        self.config.register_guild(**defaults)
        self.players = []
        self.team_manager = bot.get_cog("TeamManager")

    #region commmands

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def addPlayers(self, ctx, *players_to_add):
        """Add the players provided to the player list.

        Arguments:

        players_to_add -- One or more players in the following format:
        ```
        "['<player_id>','<wins>', '<losses>', '<elo_rating>']"
        ```
        Each player should be separated by a space.

        Examples:
        ```
        [p]addPlayers "['123456789','2', '1', '1000']"
        [p]addPlayers "['123456789','2', '1', '1000']" "['987654321','1', '2', '950']"
        ```
        """
        addedCount = 0
        try:
            for playerStr in players_to_add:
                player = ast.literal_eval(playerStr)
                playerAdded = await self._add_player(ctx, *player)
                if playerAdded:
                    addedCount += 1
                else:
                    await ctx.send("Error adding player: {0}".format(repr(player)))
        finally:
            await ctx.send("Added {0} players(s).".format(addedCount))
        await ctx.send("Done.")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def addPlayer(self, ctx, member: discord.Member, wins: int, losses: int, elo_rating: int):
        """Add a single player and their info to the file system."""
        playerAdded = await self._add_player(ctx, member, wins, losses, elo_rating)
        if(playerAdded):
            await ctx.send("Done.")
        else:
            await ctx.send("Error adding player: {0}".format(member.name))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def removePlayer(self, ctx, member: discord.Member):
        """Removes player from the file system."""
        playerRemoved = await self._remove_player(ctx, member)
        if playerRemoved:
            await ctx.send("Done.")
        else:
            await ctx.send("Error removing player: {0}".format(member.name))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearPlayers(self, ctx):
        """Removes all players from the file system."""
        await self.load_players(ctx)
        players = self.players

        players.clear()
        
        await self._save_players(ctx, players)
        await ctx.send("Done.")

    @commands.guild_only()
    @commands.command(aliases=["rr", "reportresult"])
    async def reportResult(self, ctx, member_1: discord.Member, member_1_wins: int, member_2_wins: int, member_2: discord.Member):
        """Submits the result of the game between two players. Should be used in the score report channel for your tier.
        Both players need to agree on the result before it is finalized."""
        await self.load_players(ctx)
        player_1 = self.get_player_by_id(member_1.id)
        if not player_1:
            await ctx.send("There was a problem finding player info for {}. Please verify that you have the correct member in your command. If this persists message an admin.".format(member_1.name))
            return
        player_2 = self.get_player_by_id(member_2.id)
        if not player_2:
            await ctx.send("There was a problem finding player info for {}. Please verify that you have the correct member in your command. If this persists message an admin.".format(member_2.name))
            return

        opposing_member = member_2 if ctx.author == member_1 else member_1

        if await self.verify_game_results(ctx, member_1, member_2, member_1_wins, member_2_wins, opposing_member):
            await self.finish_game(ctx, player_1, player_2, member_1_wins, member_2_wins)
            await ctx.send("Done.")

    @commands.guild_only()
    @commands.command(aliases=["arr", "adminreportresult"])
    @checks.admin_or_permissions(manage_guild=True)
    async def adminReportResult(self, ctx, member_1: discord.Member, member_1_wins: int, member_2_wins: int, member_2: discord.Member):
        """Submits the result of the game between two players. There is no verification neccessary since this is an admin-only command."""
        await self.load_players(ctx)
        player_1 = self.get_player_by_id(member_1.id)
        if not player_1:
            await ctx.send("There was a problem finding player info for {}. Please verify that you have the correct member in your command. If this persists message an admin.".format(member_1.name))
            return
        player_2 = self.get_player_by_id(member_2.id)
        if not player_2:
            await ctx.send("There was a problem finding player info for {}. Please verify that you have the correct member in your command. If this persists message an admin.".format(member_2.name))
            return

        await self.finish_game(ctx, player_1, player_2, member_1_wins, member_2_wins)
        await ctx.send("Done.")

    @commands.guild_only()
    @commands.command(aliases=["pi"])
    async def playerInfo(self, ctx, member: discord.Member):
        """Gets all the info corresponding to a player. Shows the player's wins, losses, Elo rating, the team they play for, and their team's record."""
        await self.load_players(ctx)
        player = self.get_player_by_id(member.id)
        if not player:
            ctx.send("{} has no player information at this time".format(member.name))
            return
        # TODO: Get team info for player
        await ctx.send(embed=self.embed_player_info(player))

    @commands.guild_only()
    @commands.command(aliases=["plb"])
    async def playerLeaderboard(self, ctx, tier: None):
        """Shows the top ten players in terms of current Elo rating. If tier is specified it only looks at players in that tier."""
        await self.load_players(ctx)
        players = self.players
        if not players:
            ctx.send("There are no players at this time")
            return
        # TODO: Filter list of players by tier if tier parameter is set
        players.sort(key=lambda player: player.elo_rating, reverse=True)
        await ctx.send(embed=self.embed_leaderboard(ctx, players))
    
    #endregion

    #region helper methods

    async def _add_player(self, ctx, member: discord.Member, wins: int, losses: int, elo_rating: int):
        await self.load_players(ctx)
        players = self.players
        
        # Validation of input
        # There are other validations we could do, but don't
        #     - that there aren't extra args for example
        errors = []
        if not member:
            errors.append("Member not found.")
        if wins < 0:
            errors.append("Wins cannot be a negative number.")
        if losses < 0:
            errors.append("Losses cannot be a negative number.")
        if not elo_rating:
            errors.append("Elo rating not found.")
        if errors:
            await ctx.send(":x: Errors with input:\n\n  "
                               "* {0}\n".format("\n  * ".join(errors)))
            return

        try:
            player = Player(member, wins, losses, elo_rating)
            players.append(player)
        except:
            return False
        await self._save_players(ctx, players)
        return True
    
    async def _remove_player(self, ctx, member: discord.Member):
        await self.load_players(ctx)
        players = self.players

        try:
            player = self.get_player_by_id(member.id)
            if not player:
                await ctx.send("{0} does not seem to be a current player.".format(member.name))
                return False
            players.remove(player)
        except ValueError:
            await ctx.send("{0} does not seem to be a current player.".format(member.name))
            return False
        await self._save_players(ctx, players)
        return True

    async def verify_game_results(self, ctx, member_1: discord.Member, member_2: discord.Member, member_1_wins: int, member_2_wins: int, verifier: discord.Member):
        msg = await ctx.send("{0} Please verify the results:\n**{1}** {2} - {3} **{4}**".format(verifier.mention, member_1.name,
            member_1_wins, member_2_wins, member_2.name))
        start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)
        pred = ReactionPredicate.yes_or_no(msg, verifier)
        try:
            await ctx.bot.wait_for("reaction_add", check=pred)
            if pred.result is True:
                return True
            else:
                await ctx.send(":x: Results not verified. To report the result you will need to use the `{0}reportResult` command again.".format(ctx.prefix))
                return False
        except asyncio.TimeoutError:
            await ctx.send(":x: Result not verified in time. To report the result you will need to use the `{0}reportResult` command again.".format(ctx.prefix))
            return False
    
    async def finish_game(self, ctx, player_1, player_2, player_1_wins: int, player_2_wins: int):
        player_1_new_elo, player_2_new_elo = self.update_elo(player_1.elo_rating, player_2.elo_rating, player_1_wins / (player_1_wins + player_2_wins))
        await ctx.send(embed=self.embed_game_results(player_1, player_1_wins, player_2_wins, player_2, player_1_new_elo, player_2_new_elo))
        self.update_player_info(player_1, player_1_wins, player_2_wins, player_1_new_elo)
        self.update_player_info(player_2, player_2_wins, player_1_wins, player_2_new_elo)
        await self._save_players(ctx, self.players)
    
    def update_elo(self, player_1_elo: int, player_2_elo: int, result: float):
        """Calculates and returns the new Elo ratings for the two players based on their match results and the K-factor.
        Result param should be a decimal between 0 and 1 relating to the match results for player 1, i.e. a result of 1 
        means player 1 won all the games in the match, a result of .25 means player 1 won 25% of the games in the match, etc."""
        elo_dif = int(player_1_elo) - int(player_2_elo)
        exponent = -1 * (elo_dif / 100)
        expectation = 1 / (1 + pow(10, exponent))
        player_1_new_elo = round(int(player_1_elo) + (k_factor * (result - expectation)))
        player_2_new_elo = round(int(player_2_elo) + (k_factor * ((1 - result) - (1 - expectation))))
        return player_1_new_elo, player_2_new_elo
    
    def update_player_info(self, player, new_wins, new_losses, new_elo_rating):
        player.wins += new_wins
        player.losses += new_losses
        player.elo_rating = new_elo_rating

    def get_player_by_id(self, member_id):
        for player in self.players:
            if player.member.id == member_id:
                return player
        return None

    async def match_info_helper(self, ctx):
        await self.load_players(ctx)
        if self.players:
            return True
        return False

    #endregion

    #region embed methods

    def embed_player_info(self, player):
        embed = discord.Embed(title="{0}".format(player.member.name), color=discord.Colour.blue())
        embed.set_thumbnail(url=player.member.avatar_url)
        embed.add_field(name="Games Played", value="{}\n".format(player.wins + player.losses), inline=True)
        embed.add_field(name="Record", value="{0} - {1}\n".format(player.wins, player.losses), inline=True)
        embed.add_field(name="Elo Rating", value="{}\n".format(player.elo_rating), inline=True)
        return embed

    def embed_leaderboard(self, ctx, sorted_players):
        embed = discord.Embed(title="{0} Player Leaderboard".format(ctx.guild.name), color=discord.Colour.blue())
        
        index = 1
        message = ""
        for player in sorted_players:
            message += "`{0}` __**{1}:**__ **Elo Rating:** {2}  **Record:** {3} - {4}  **Games Played:** {5}\n".format(index, player.member.mention, player.elo_rating, 
            player.wins, player.losses, player.wins + player.losses)
            
            index += 1
            if index > 10:
                break

        embed.add_field(name="Highest Elo Rating", value=message, inline=True)
        return embed

    def embed_game_results(self, player_1, player_2, player_1_wins: int, player_2_wins: int, player_1_new_elo, player_2_new_elo):
        embed = discord.Embed(title="{0} vs. {1}".format(player_1.member.name, player_2.member.name), color=discord.Colour.blue())
        embed.add_field(name="Result", value="**{0}** {1} - {2} **{3}**\n".format(player_1.member.name, player_1_wins, player_2_wins, player_2.member.name), inline=True)
        embed.add_field(name="Updated Elo Rating", value="**{0}** = {1} ({2})\n**{3}** = {4} ({5})\n".format(player_1.member.name, player_1_new_elo, player_1_new_elo - player_1.elo_rating,
            player_2.member.name, player_2_new_elo, player_2_new_elo - player_2.elo_rating), inline=True)
        return embed

    #endregion

    #region load/save methods

    async def load_players(self, ctx, force_load = False):
        if self.players is None or self.players == [] or force_load:
            players = await self._players(ctx)
            player_list = []
            for value in players.values():
                member = ctx.guild.get_member(value["Id"])
                wins = value["Wins"]
                losses = value["Losses"]
                elo_rating = value["EloRating"]
                player = Player(member, wins, losses, elo_rating)
                player_list.append(player)

            self.players = player_list

    async def _players(self, ctx):
        return await self.config.guild(ctx.guild).Players()

    async  def _save_players(self, ctx, players):
        player_dict = {}
        for player in players:
            player_dict[player.member.id] = player._to_dict()
        await self.config.guild(ctx.guild).Players.set(player_dict)

    #endregion

class Player:
    def __init__(self, member, wins: int, losses: int, elo_rating: int):
        self.member = member
        self.wins = wins
        self.losses = losses
        self.elo_rating = elo_rating

    def _to_dict(self):
        return {
            "Id": self.member.id,
            "Wins": self.wins,
            "Losses": self.losses,
            "EloRating": self.elo_rating
        }