import discord
import asyncio
import uuid
import ast

from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions, menu, DEFAULT_CONTROLS

k_factor = 40

defaults = {"Players": {}, "Results": [], "SelfReportFlag": False}

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
        Both players need to agree on the result before it is finalized. 
        
        This command may be disabled by admins to prevent erroneous reporting."""
        if not self._self_report_flag(ctx):
            await ctx.send("Score reporting for this server is currently set to admin only.")
            return
        await self.load_players(ctx)
        player_1 = self.get_player_by_id(self.players, member_1.id)
        if not player_1:
            await ctx.send("There was a problem finding player info for {}. Please verify that you have the correct member in your command. If this persists message an admin.".format(member_1.name))
            return
        player_2 = self.get_player_by_id(self.players, member_2.id)
        if not player_2:
            await ctx.send("There was a problem finding player info for {}. Please verify that you have the correct member in your command. If this persists message an admin.".format(member_2.name))
            return

        opposing_member = member_2 if ctx.author == member_1 else member_1

        if await self.verify_game_results(ctx, member_1, member_2, member_1_wins, member_2_wins, opposing_member):
            await self.finish_game(ctx, player_1, player_2, member_1_wins, member_2_wins)
            await ctx.send("Done.")

    @commands.guild_only()
    @commands.command(aliases=["arrs", "adminreportresults"])
    @checks.admin_or_permissions(manage_guild=True)
    async def adminReportResults(self, ctx, *match_results):
        """Submits results for matches in bulk with no verification.

        Arguments:

        match_results -- One or more match results in the following format:
        ```
        "['<member_1>','<member_1_wins>', '<member_2_wins>', '<member_2>']"
        ```
        Each match should be separated by a space.
        Members can be either their id number, their name, their name + descriminator, or a mention of the user.
        Id number is preferred as it's guaranteed to be unique.

        Examples:
        ```
        [p]adminReportResults "['123456789','2', '1', '987654321']"
        [p]adminReportResults "['123456789','2', '1', '987654321']" "['234567890','1', '2', '098765432']"
        ```
        """
        addedCount = 0
        try:
            for matchStr in match_results:
                match = ast.literal_eval(matchStr)
                matchSubmitted = await self._admin_report_result(ctx, *match)
                if matchSubmitted:
                    addedCount += 1
                else:
                    await ctx.send("Error submitting match: {0}".format(repr(match)))
        finally:
            await ctx.send("Submitted {0} match(es).".format(addedCount))
        await ctx.send("Done.")

    @commands.guild_only()
    @commands.command(aliases=["arr", "adminreportresult"])
    @checks.admin_or_permissions(manage_guild=True)
    async def adminReportResult(self, ctx, member_1: discord.Member, member_1_wins: int, member_2_wins: int, member_2: discord.Member):
        """Submits the result of the game between two players. There is no verification neccessary since this is an admin-only command."""
        if await self._admin_report_result(ctx, member_1, member_1_wins, member_2_wins, member_2):
            await ctx.send("Done.")

    @commands.guild_only()
    @commands.command(aliases=["pi"])
    async def playerInfo(self, ctx, member: discord.Member = None):
        """Gets all the info corresponding to a player. Shows the player's wins, losses, Elo rating, the team they play for."""
        await self.load_players(ctx)
        if not member:
            member = ctx.author
        player = self.get_player_by_id(self.players, member.id)
        if not player:
            ctx.send("{} has no player information at this time".format(member.name))
            return
        team_name = await self.team_manager.get_current_team_name(ctx, member)
        await ctx.send(embed=self.embed_player_info(player, team_name))

    @commands.guild_only()
    @commands.command(aliases=["plb"])
    async def playerLeaderboard(self, ctx, tier = None):
        """Shows the top ten players in terms of current Elo rating. If tier is specified it only looks at players in that tier."""
        await self.load_players(ctx)
        players = self.players
        if not players:
            ctx.send("There are no players at this time")
            return
        
        tier_role = None

        #Filter list by tier if given
        if tier:
            tier_role = self.team_manager._get_tier_role(ctx, tier)
            if tier_role:
                tier_players = []
                for player in players:
                    if tier_role in player.member.roles:
                        tier_players.append(player)
                players = tier_players

        players.sort(key=lambda player: player.elo_rating, reverse=True)
        await ctx.send(embed=self.embed_leaderboard(ctx, players, tier_role))

    @commands.guild_only()
    @commands.command(aliases=["toggleReport", "toggleSelfReporting", "toggleSR", "toggleselfreport", "togglesr", "tsr"])
    @checks.admin_or_permissions(manage_guild=True)
    async def toggleSelfReport(self, ctx):
        """
        Toggles the status of the self report flag. (Default: False)
        If True, players can report their own results and results must be verified by the opposing player.
        If False, only admins can report results and no verification is needed.
        """
        self_report_flag = await self._toggle_self_report_flag(ctx.guild)
        self_report_str = "on" if self_report_flag else "off"
        await ctx.send("Self reporting is now **{0}**.".format(self_report_str))

    @commands.guild_only()
    @commands.command(aliases=["getallplayers", "gap", "getAllPlayerRatings", "listAllPlayers", "listAllPlayerRatings"])
    @checks.admin_or_permissions(manage_guild=True)
    async def getAllPlayers(self, ctx):
        await self.load_players(ctx)
        players = self.players
        if not players:
            await ctx.send("There are no players at this time")
            return

        messages = []
        message = ""
        for player in players:
            player_string = "{0.member.id}:{0.wins}:{0.losses}:{0.elo_rating}\n".format(player)
            if len(message + player_string) < 2000:
                message += player_string
            else:
                messages.append(message)
                message = player_string
        messages.append(message)
        for msg in messages:
            if msg:
                await ctx.send("{0}{1}{0}".format("```", msg))

    
#endregion

#region helper methods

    async def _add_player(self, ctx, member, wins, losses, elo_rating):
        await self.load_players(ctx)
        players = self.players
        
        wins = int(wins)
        losses = int(losses)
        elo_rating = int(elo_rating)

        # Validation of input
        # There are other validations we could do, but don't
        #     - that there aren't extra args for example
        errors = []
        if not isinstance(member, discord.Member):
            try:
                member = await commands.MemberConverter().convert(ctx, member)
            except:
                errors.append("Member {} not found.".format(member))
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
            player = Player(member, wins, losses, elo_rating, -1)
            players.append(player)
        except:
            return False
        await self._save_players(ctx, players)
        return True
    
    async def _remove_player(self, ctx, member: discord.Member):
        await self.load_players(ctx)
        players = self.players

        try:
            player = await self.get_player_by_id(self.players, member.id)
            if not player:
                await ctx.send("{0} does not seem to be a current player.".format(member.name))
                return False
            players.remove(player)
        except ValueError:
            await ctx.send("{0} does not seem to be a current player.".format(member.name))
            return False
        await self._save_players(ctx, players)
        return True

    async def _admin_report_result(self, ctx, member_1: discord.Member, member_1_wins: int, member_2_wins: int, member_2: discord.Member):
        await self.load_players(ctx)
        player_1 = self.get_player_by_id(self.players, member_1.id)
        if not player_1:
            await ctx.send("There was a problem finding player info for {}. Please verify that you have the correct member in your command. If this persists message an admin.".format(member_1.name))
            return False
        player_2 = self.get_player_by_id(self.players, member_2.id)
        if not player_2:
            await ctx.send("There was a problem finding player info for {}. Please verify that you have the correct member in your command. If this persists message an admin.".format(member_2.name))
            return False

        await self.finish_game(ctx, player_1, player_2, member_1_wins, member_2_wins)
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
        await ctx.send(embed=self.embed_game_results(player_1, player_2, player_1_wins, player_2_wins, player_1_new_elo, player_2_new_elo))
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

    def get_player_by_id(self, players, member_id):
        for player in players:
            if player.member.id == member_id:
                return player
        return None

    async def get_player_record_and_rating_by_id(self, ctx, member_id):
        await self.load_players(ctx)
        player = self.get_player_by_id(self.players, member_id)
        if player:
            return (player.wins, player.losses, player.elo_rating)
        return None

    async def guild_has_players(self, ctx):
        await self.load_players(ctx)
        if self.players:
            return True
        return False

    async def get_player_seed(self, ctx, user_team_name):
        user = ctx.author
        if not self.team_manager.is_subbed_out(user):
            active_members = await self.team_manager.get_active_members_by_team_name(ctx, user_team_name)
            sorted_members = await self.sort_members_by_rating(ctx, active_members)
            try:
                return sorted_members.index(user) + 1
            except:
                return None
        return None

    async def get_member_by_team_and_seed(self, ctx, team_name, seed):
        active_members = await self.team_manager.get_active_members_by_team_name(ctx, team_name)
        sorted_members = await self.sort_members_by_rating(ctx, active_members)
        return sorted_members[seed - 1]

    async def get_ordered_opponent_names_and_seeds(self, ctx, seed, is_home, opposing_team_name):
        ordered_opponent_names = []
        ordered_opponent_seeds = []
        active_opponents = await self.team_manager.get_active_members_by_team_name(ctx, opposing_team_name)
        sorted_opponents = await self.sort_members_by_rating(ctx, active_opponents)
        if is_home:
            if seed == 1:
                ordered_opponent_names.append(sorted_opponents[2].nick)
                ordered_opponent_names.append(sorted_opponents[1].nick)
                ordered_opponent_names.append(sorted_opponents[0].nick)
                ordered_opponent_seeds = [3, 2, 1]
            elif seed == 2:
                ordered_opponent_names.append(sorted_opponents[0].nick)
                ordered_opponent_names.append(sorted_opponents[2].nick)
                ordered_opponent_names.append(sorted_opponents[1].nick)
                ordered_opponent_seeds = [1, 3, 2]
            else:
                ordered_opponent_names.append(sorted_opponents[1].nick)
                ordered_opponent_names.append(sorted_opponents[0].nick)
                ordered_opponent_names.append(sorted_opponents[2].nick)
                ordered_opponent_seeds = [2, 1, 3]
        else:
            if seed == 1:
                ordered_opponent_names.append(sorted_opponents[1].nick)
                ordered_opponent_names.append(sorted_opponents[2].nick)
                ordered_opponent_names.append(sorted_opponents[0].nick)
                ordered_opponent_seeds = [2, 3, 1]
            elif seed == 2:
                ordered_opponent_names.append(sorted_opponents[2].nick)
                ordered_opponent_names.append(sorted_opponents[0].nick)
                ordered_opponent_names.append(sorted_opponents[1].nick)
                ordered_opponent_seeds = [3, 1, 2]
            else:
                ordered_opponent_names.append(sorted_opponents[0].nick)
                ordered_opponent_names.append(sorted_opponents[1].nick)
                ordered_opponent_names.append(sorted_opponents[2].nick)
                ordered_opponent_seeds = [1, 2, 3]
        return (ordered_opponent_names, ordered_opponent_seeds)

    async def sort_members_by_rating(self, ctx, member_list):
        await self.load_players(ctx)
        if not self.players:
            return member_list
        players = []
        for member in member_list:
            players.append(self.get_player_by_id(self.players, member.id))
        players.sort(key=lambda player: max(player.elo_rating, player.temp_rating), reverse=True)
        sorted_members = []
        for player in players:
            sorted_members.append(player.member)
        return sorted_members

    async def set_player_temp_rating(self, ctx, subbed_member, subbed_out_member):
        await self.load_players(ctx)
        if self.players:
            subbed_player = self.get_player_by_id(self.players, subbed_member.id)
            subbed_out_player = self.get_player_by_id(self.players, subbed_out_member.id)
            if subbed_player and subbed_out_player:
                subbed_player.temp_rating = subbed_out_player.elo_rating
                await self._save_players(ctx, self.players)
                return True
        return False

    async def reset_temp_rating(self, ctx, member):
        await self.load_players(ctx)
        if self.players:
            player = self.get_player_by_id(self.players, member.id)
            if player:
                player.temp_rating = -1
                await self._save_players(ctx, self.players)
        return False

#endregion

#region embed methods

    def embed_player_info(self, player, team_name):
        embed = discord.Embed(title="{0}".format(player.member.nick), color=discord.Colour.blue())
        embed.set_thumbnail(url=player.member.avatar_url)
        embed.add_field(name="Games Played", value="{}\n".format(player.wins + player.losses), inline=False)
        embed.add_field(name="Record", value="{0} - {1}\n".format(player.wins, player.losses), inline=False)
        embed.add_field(name="Elo Rating", value="{}\n".format(player.elo_rating), inline=False)
        embed.add_field(name="Team", value="{}\n".format(team_name), inline=False)
        return embed

    def embed_leaderboard(self, ctx, sorted_players, tier_role):
        embed_color = discord.Colour.blue()
        embed_name = ctx.guild.name
        if tier_role:
            embed_color = tier_role.color
            embed_name = tier_role.name
        embed = discord.Embed(title="{0} Player Leaderboard".format(embed_name), color=embed_color)
        
        index = 1
        message = ""
        for player in sorted_players:
            message += "`{0}` __**{1}:**__ **Elo Rating:** {2}  **Record:** {3} - {4}  **Games Played:** {5}\n".format(index, player.member.nick, player.elo_rating, 
            player.wins, player.losses, player.wins + player.losses)
            
            index += 1
            if index > 10:
                break

        embed.add_field(name="Highest Elo Rating", value=message, inline=False)
        return embed

    def embed_game_results(self, player_1, player_2, player_1_wins: int, player_2_wins: int, player_1_new_elo, player_2_new_elo):
        embed = discord.Embed(title="{0} vs. {1}".format(player_1.member.nick, player_2.member.nick), color=discord.Colour.blue())
        embed.add_field(name="Result", value="**{0}** {1} - {2} **{3}**\n".format(player_1.member.nick, player_1_wins, player_2_wins, player_2.member.nick), inline=False)
        embed.add_field(name="Updated Elo Rating", value="**{0}** = {1} ({2})\n**{3}** = {4} ({5})\n".format(player_1.member.nick, player_1_new_elo, player_1_new_elo - int(player_1.elo_rating),
            player_2.member.nick, player_2_new_elo, player_2_new_elo - int(player_2.elo_rating)), inline=False)
        return embed

#endregion

#region load/save methods

    async def load_players(self, ctx, force_load = False):
        players = await self._players(ctx)
        player_list = []
        remove_player = False
        for value in players.values():
            member = ctx.guild.get_member(value["Id"])
            if not member:
                # Member not found in server, don't add to list of players and 
                # re-save list at the end to ensure they get removed
                remove_player = True
                continue
            wins = value["Wins"]
            losses = value["Losses"]
            elo_rating = value["EloRating"]
            temp_rating = value["TempRating"]
            player = Player(member, wins, losses, elo_rating, temp_rating)
            player_list.append(player)

        self.players = player_list
        if remove_player:
            await self._save_players(ctx, self.players)

    async def _players(self, ctx):
        return await self.config.guild(ctx.guild).Players()

    async  def _save_players(self, ctx, players):
        player_dict = {}
        for player in players:
            player_dict[player.member.id] = player._to_dict()
        await self.config.guild(ctx.guild).Players.set(player_dict)

    async def _toggle_self_report_flag(self, guild):
        self_report_flag = not await self._self_report_flag(guild)
        await self.config.guild(guild).SelfReportFlag.set(self_report_flag)
        return self_report_flag

    async def _self_report_flag(self, guild):
        return await self.config.guild(guild).SelfReportFlag()

#endregion

class Player:
    def __init__(self, member, wins: int, losses: int, elo_rating: int, temp_rating: int):
        self.member = member
        self.wins = wins
        self.losses = losses
        self.elo_rating = elo_rating
        # Used for temp subs to ensure they take the same seed as the player they replace
        # Default is -1, meaning there is no temp_rating set
        self.temp_rating = temp_rating

    def _to_dict(self):
        return {
            "Id": self.member.id,
            "Wins": self.wins,
            "Losses": self.losses,
            "EloRating": self.elo_rating,
            "TempRating": self.temp_rating
        }