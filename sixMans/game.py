import random
import struct
from typing import List
import uuid
import asyncio
import operator

import discord

from .strings import Strings
from .queue import SixMansQueue


SELECTION_MODES  = {
    0x1F3B2: Strings.RANDOM_TS,     # game_die
    0x1F1E8: Strings.CAPTAINS_TS,   # C
    0x0262F: Strings.BALANCED_TS,   # Ying&Yang
}

class Game:
    def __init__(
            self, players, queue: SixMansQueue,
            helper_role=None,
            automove=False,
            text_channel: discord.TextChannel=None, 
            voice_channels: List[discord.VoiceChannel]=[],
            info_message: discord.Message=None,
            observers=None):
        self.id = uuid.uuid4().int
        self.players = set(players)
        self.captains = []
        self.blue = set()
        self.orange = set()
        self.roomName = self._generate_name_pass()
        self.roomPass = self._generate_name_pass()
        self.queue = queue
        self.scoreReported = False
        self.teamSelection = queue.teamSelection
        self.game_state = Strings.TEAM_SELECTION_GS
        
        # Optional params
        self.helper_role = helper_role
        self.automove = automove
        self.textChannel = text_channel
        self.voiceChannels = voice_channels #List of voice channels: [Blue, Orange]
        self.info_message = info_message
        self.observers = observers if observers else []

        # attatch listeners to game
        for observer in self.observers:
            observer._subject = self
    
        asyncio.create_task(self._notify())
        # asyncio.create_task(self.create_game_channels())
        # asyncio.create_task(self.process_team_selection_method())
        
        if self.teamSelection.lower() == Strings.VOTE_TS.lower():
            self.vote = None
        
    # @property
    # def subject_state(self):
    #     return self.game_state

    async def _notify(self, new_state=None):
        if new_state:
            self.game_state = new_state
        for observer in self.observers:
            try:
                await observer.update(self)
            except:
                #TODO: Log error without preventing code from continuing to run
                pass

# Team Management
    async def create_game_channels(self, category=None):
        guild = self.queue.guild
        # sync permissions on channel creation, and edit overwrites (@everyone) immediately after
        code = str(self.id)[-3:]
        self.textChannel = await guild.create_text_channel(
            "{} {} {} Mans".format(code, self.queue.name, self.queue.queueMaxSize), 
            permissions_synced=True,
            category=category
        )
        await self.textChannel.set_permissions(guild.default_role, view_channel=False, read_messages=False)
        for player in self.players:
            await self.textChannel.set_permissions(player, read_messages=True)
        blue_vc = await guild.create_voice_channel("{} | {} Blue Team".format(code, self.queue.name), permissions_synced=True, category=category)
        await blue_vc.set_permissions(guild.default_role, connect=False)
        oran_vc = await guild.create_voice_channel("{} | {} Orange Team".format(code, self.queue.name), permissions_synced=True, category=category)
        await oran_vc.set_permissions(guild.default_role, connect=False)
        
        # manually add helper role perms if one is set
        if self.helper_role:
            await self.textChannel.set_permissions(self.helper_role, view_channel=True, read_messages=True)
            await blue_vc.set_permissions(self.helper_role, connect=True)
            await oran_vc.set_permissions(self.helper_role, connect=True)
        
        self.voiceChannels = [blue_vc, oran_vc]

        # Mentions all players
        await self.textChannel.send(', '.join(player.mention for player in self.players))

    async def add_to_blue(self, player):
        self.players.remove(player)
        self.blue.add(player)

        blue_vc, orange_vc = self.voiceChannels
        await blue_vc.set_permissions(player, connect=True)
        await orange_vc.set_permissions(player, connect=False)

        if self.automove:
            try:
                await player.move_to(blue_vc)
            except:
                pass

    async def add_to_orange(self, player):
        self.players.remove(player)
        self.orange.add(player)

        blue_vc, orange_vc = self.voiceChannels
        await blue_vc.set_permissions(player, connect=False)
        await orange_vc.set_permissions(player, connect=True)

        if self.automove:
            try:
                await player.move_to(orange_vc)
            except:
                pass

# Team Selection
    async def vote_team_selection(self, helper_role=None):
        # Mentions all players
        embed = self._get_vote_embed()
        self.info_message = await self.textChannel.send(embed=embed)
        reacts = [hex(key) for key in SELECTION_MODES.keys()]
        await self._add_reactions(reacts, self.info_message)

    async def pick_balanced_teams(self):
        balanced_teams, balance_score = self.get_balanced_teams()
        self.balance_score = balance_score
        # Pick random balanced team
        blue = random.choice(balanced_teams)
        orange = []
        for player in self.players:
            if player not in blue:
                orange.append(player)
        for player in blue:
            await self.add_to_blue(player)
        for player in orange:
            await self.add_to_orange(player)
        
        self.reset_players()
        self.get_new_captains_from_teams()

        await self.update_game_info()
        
    async def pick_random_teams(self):
        self.blue = set()
        self.orange = set()
        for player in random.sample(self.players, int(len(self.players)/2)):
            await self.add_to_orange(player)
        blue = [player for player in self.players]
        for player in blue:
            await self.add_to_blue(player)
        self.reset_players()
        self.get_new_captains_from_teams()

        await self.update_game_info()

    async def shuffle_players(self):
        await self.pick_random_teams()
        await self.info_message.add_reaction(Strings.SHUFFLE_REACT)

    async def captains_pick_teams(self, helper_role=None):
        if not helper_role:
            helper_role = self.helper_role
        
        # Pick captains
        self.captains = random.sample(self.players, 2)
        self.blue.add(self.captains[0])
        self.orange.add(self.captains[1])
        self.helper_role = helper_role

        pick_order = ['blue', 'orange', 'orange']

        pickable = list(self.players)
        pickable.remove(self.captains[0])
        pickable.remove(self.captains[1])

        # Assign reactions to remaining players
        self.react_player_picks = {}
        react_hex = 0x1F1E6
        for i in range(len(pickable)):
            react_hex_i = hex(react_hex+i)
            self.react_player_picks[react_hex_i] = pickable[i]
        
        # Get player pick embed
        embed = self._get_captains_embed('blue')
        self.info_message = await self.textChannel.send(embed=embed)
        
        await self._add_reactions(self.react_player_picks.keys(), self.info_message)

# Team Selection helpers
    async def process_team_selection_method(self):
        helper_role = self.helper_role
        if self.teamSelection.lower() == Strings.VOTE_TS.lower():
            await self.vote_team_selection()
        elif self.teamSelection.lower() == Strings.CAPTAINS_TS.lower():
            await self.captains_pick_teams(helper_role)
        elif self.teamSelection.lower() == Strings.RANDOM_TS.lower():
            await self.pick_random_teams()
        elif self.teamSelection.lower() == Strings.SHUFFLE_TS.lower():
            await self.shuffle_players()
        elif self.teamSelection.lower() == Strings.BALANCED_TS.lower():
            await self.pick_balanced_teams()
        else:
            return print("you messed up fool: {}".format(self.teamSelection))

    async def process_captains_pick(self, reaction, user):
        teams_complete = False
        pick_i = len(self.blue)+len(self.orange)-2
        pick_order = ['blue', 'orange', 'orange', 'blue']
        pick = pick_order[pick_i%len(pick_order)]
        captain_picking = self.captains[0] if pick == 'blue' else self.captains[1]
        
        if user != captain_picking:
            return False
        
        # get player from reaction
        player_picked = self._get_player_from_reaction_emoji(ord(reaction.emoji))
        await self.info_message.clear_reaction(reaction.emoji)
        
        # add to correct team, update teams embed
        self.blue.add(player_picked) if pick == 'blue' else self.orange.add(player_picked)
        
        # TODO: automatically process last pick
        picks_remaining = list(self.react_player_picks.keys())
        if len(picks_remaining) > 1:
            embed = self._get_captains_embed(pick_order[pick_i+1])
            await self.info_message.edit(embed=embed)
        
        elif len(picks_remaining) == 1:
            last_pick = 'blue' if len(self.orange) > len(self.blue) else 'orange'
            last_pick_key = picks_remaining[0]
            last_player = self.react_player_picks[last_pick_key]
            del self.react_player_picks[last_pick_key]
            await self.info_message.clear_reactions()
            self.blue.add(last_player) if last_pick == 'blue' else self.orange.add(last_player)
            teams_complete = True
            embed = self._get_captains_embed(None, guild=last_player.guild)
            await self.info_message.edit(embed=embed)
        
        if teams_complete:
            for player in self.blue:
                await self.add_to_blue(player)
            for player in self.orange:
                await self.add_to_orange(player)
            self.reset_players()
            await self.update_game_info()
        
        return teams_complete
    
    async def process_team_select_vote(self, reaction, member, added=True):
        if member not in self.players:
            return

        if self._hex_i_from_emoji(reaction.emoji) not in SELECTION_MODES:
            return 
        
        # COUNT UP VOTE TOTALS
        if not self.vote:
            self.vote = [None, 0]

        # RECORD VOTES
        self.info_message = await self.textChannel.fetch_message(self.info_message.id)
        votes = {}
        for this_react in self.info_message.reactions:
            # here maybe
            react_hex_i = self._hex_i_from_emoji(this_react.emoji)
            if react_hex_i in SELECTION_MODES:
                reacted_members = await this_react.users().flatten()
                count = this_react.count - 1
                if added and this_react.emoji != reaction.emoji and member in reacted_members:
                    await this_react.remove(member)
                    count -= 1
                votes[react_hex_i] = {'count': count, 'emoji': this_react.emoji}

        # Update embed
        embed = self._get_vote_embed(votes)
        await self.info_message.edit(embed=embed)

        # COUNT VOTES - Check if complete
        total_votes = 0
        runner_up = 0
        running_vote = [None, 0]

        for react_hex, data in votes.items():
            num_votes = data['count']
            if num_votes > running_vote[1]:
                runner_up = running_vote[1]
                running_vote = [react_hex, num_votes]

            elif num_votes > runner_up and num_votes <= running_vote[1]:
                runner_up = num_votes

            total_votes += num_votes
        
        # track top vote
        if running_vote[1] > self.vote[1]:
            self.vote = running_vote
        
        pending_votes = len(self.players) - total_votes

        voted_mode = None
        # Vote Complete if...
        # here
        if added and member.name == 'nullidea' or (pending_votes == 0 or (pending_votes + runner_up) <= self.vote[1]):
            # action and update first - help with race conditions
            voted_mode = SELECTION_MODES[self.vote[0]]
            if self.teamSelection.lower() == Strings.VOTE_TS.lower():
                self.teamSelection = voted_mode
                # await self.textChannel.send(self.teamSelection)
                embed = self._get_vote_embed(vote=votes, winning_vote=self.vote[0])
                await self.info_message.edit(embed=embed)
                await self.process_team_selection_method()
            else:
                # in case of weird stuff? This should never be hit.
                embed = self._get_vote_embed(vote=votes, winning_vote=self.vote[0])
                await self.info_message.edit(embed=embed)

            # Next Step: Select Teams
            return voted_mode

    def get_balanced_teams(self):
        # Get relevent info from helpers
        player_scores = self.get_player_scores()
        team_combos = self.get_team_combos()

        # Calc perfectly balanced team based on scores
        score_total = 0
        for player, p_data in player_scores.items():
            score_total += p_data['Score']
        avg_team_score = score_total/(len(self.players)/2)

        # Determine balanced teams
        balanced_teams = []
        balance_diff = None
        for a_team in team_combos:
            team_score = 0
            for player in a_team:
                team_score += player_scores[player]['Score']
            
            team_diff = abs(avg_team_score - team_score)
            if balance_diff:
                if team_diff < balance_diff:
                    balance_diff == team_diff
                    balanced_teams = [a_team]
                elif team_diff == balance_diff:
                    balanced_teams.append(a_team)
            else:
                balance_diff == team_diff
                balanced_teams = [a_team]
        
        # return balanced team
        return balanced_teams, team_diff

    def get_player_scores(self):
        # Get Player Stats
        scores = {}
        ranked_players = 0
        rank_total = 0
        wp_players = 0
        wp_total = 0
        for player in self.players:
            player_stats = self.queue.get_player_summary(player)

            rank = 1  # get_player_rank
            if player_stats:
                p_wins = player_stats['Wins']
                p_losses = player_stats['GamesPlayed'] - p_wins
                qwp = round(self._get_wp(p_wins, p_losses), 2)
            else:
                qwp = None

            scores[player] = {"Rank": rank, "QWP": qwp}
            if rank: 
                ranked_players += 1
                rank_total += rank 
            if qwp:
                wp_players += 1
                wp_total += qwp
        
        rank_avg = rank_total/ranked_players if ranked_players else 1
        
        # Score Players, Avg
        score_total = 0
        for player, p_data in scores.items():
            p_rank = p_data['Rank'] if ('Rank' in p_data and p_data['Rank']) else rank_avg
            p_wp = p_data['QWP'] if ('QWP' in p_data and p_data['QWP']) else 0.5
            score_adj = (p_wp * 2) - 1  # +/- 1
            
            score = p_rank + score_adj 
            p_data['Score'] = score
            score_total += score
        return scores 

    def get_team_combos(self):
        team_lineups = []
        players = self.players
        for a_player in players:
            for b_player in players:
                for c_player in players:
                    lineup = list(set([a_player, b_player, c_player]))
                    # lineup.sort()
                    lineup = sorted(lineup, key=operator.attrgetter('id'))
                    if (len(lineup) == len(players)/2) and lineup not in team_lineups:
                        team_lineups.append(lineup)
        return team_lineups

    def _get_vote_embed(self, vote=None, winning_vote=None):
        if not vote:
            vote = {}
            # Skeleton Vote if no votes
            for react_hex, mode in SELECTION_MODES.items():
                react_emoji = self._get_pick_reaction(react_hex)
                vote[react_hex] = {'count': 0, 'emoji': react_emoji}
            
        # Count Votes, prep embed fields
        vote_options = []
        votes_casted = []
        total_votes = 0
        for react_hex, mode in SELECTION_MODES.items():
            react_emoji = self._get_pick_reaction(react_hex)
            vote_options.append("{} {}".format(react_emoji, mode))
            try:
                num_votes = vote[react_hex]['count']
            except:
                num_votes = 0
            votes_casted.append(str(num_votes))
            total_votes += num_votes

        pending = len(self.players) - total_votes
        description = "Please vote for your preferred team selection method!"
        embed = discord.Embed(
            title="{} Game | Team Selection Vote".format(self.textChannel.name.replace('-', ' ').title()[4:]),
            color=self._get_completion_color(total_votes, pending),
            description=description
        )

        # embed.add_field()
        embed.add_field(name="Options", value='\n'.join(vote_options), inline=True)
        embed.add_field(name="Votes", value='\n'.join(votes_casted), inline=True)
        
        if winning_vote:
            voted = "{} {}".format(self._get_pick_reaction(winning_vote), SELECTION_MODES[winning_vote])
            embed.add_field(name="Vote Complete!", value=voted, inline=False)
        
        help_message = "If you think the bot isn't working correctly or have suggestions to improve it, please contact adammast."
        if self.helper_role:
            help_message = "If you need any help or have questions please contact someone with the {0} role. ".format(self.helper_role.mention) + help_message
        embed.add_field(name="Help", value=help_message, inline=False)
        
        embed.set_footer(text="Game ID: {}".format(self.id))
        return embed

    def _get_captains_embed(self, pick, guild=None):
        # Determine who picks next
        if pick:
            team_color = discord.Colour.blue() if pick == 'blue' else discord.Colour.orange()
            player = self.captains[0] if pick == 'blue' else self.captains[1]
            description = "**{}**, react to pick a player to join the **{}** team.".format(player.name, pick)

        else:
            team_color = discord.Colour.green()
            description="Teams have been set!"

        embed = discord.Embed(
            title="{} Game | Team Selection".format(self.textChannel.name.replace('-', ' ').title()[4:]),
            color=team_color,
            description=description
        )
        ts_emoji = self._get_ts_emoji()
        embed.add_field(name="Team Selection", value="{} {}".format(ts_emoji, self.teamSelection), inline=False)

        if pick:
            embed.set_thumbnail(url=player.avatar_url)
        elif guild:
            embed.set_thumbnail(url=guild.icon_url)

        # List teams as they stand
        embed.add_field(name="Blue Team", value=', '.join(p.mention for p in self.blue), inline=False)
        embed.add_field(name="Orange Team", value=', '.join(p.mention for p in self.orange), inline=False)

        # List available players
        pickable_players = self._get_pickable_players_str()
        if pickable_players:
            embed.add_field(name="Available Players", value=pickable_players, inline=False)
        
        if self.helper_role:
            embed.add_field(name="Help", value="If you need any help or have questions please contact someone with the {} role.".format(self.helper_role.mention))
        
        embed.set_footer(text="Game ID: {}".format(self.id))

        return embed
    
    def _hex_i_from_emoji(self, emoji):
        return ord(emoji)

    async def report_winner(self, winner):
        await self.color_embed_for_winners(winner)
        await self._notify(new_state=Strings.GAME_OVER_GS)

    async def color_embed_for_winners(self, winner):
        if self.info_message is not None:
            winner = winner.lower()
            if winner == 'blue':
                color = discord.Colour.blue()
            elif winner == 'orange':
                color = discord.Colour.orange()
            else:
                color = discord.Colour.green()  # catch all for errors hopefully

            embed = self.info_message.embeds[0]
            embed_dict = embed.to_dict()
            embed_dict['color'] = color.value
            embed = discord.Embed.from_dict(embed_dict)
            await self.info_message.edit(embed=embed)

    def _get_player_from_reaction_emoji(self, emoji):
        target_key = None
        target_value = None
        for e, player in self.react_player_picks.items():
            if emoji == int(e, base=16): # or ord(emoji) == ord(e) or str(emoji) == str(e):
                target_key = e
                target_value = player
                break
        if target_key:
            del self.react_player_picks[target_key]
        return target_value

    def _get_pick_reaction(self, int_or_hex):
        try:
            if type(int_or_hex) == int:
                return struct.pack('<I', int_or_hex).decode('utf-32le')
            if type(int_or_hex) == str:
                return struct.pack('<I', int(int_or_hex, base=16)).decode('utf-32le') # i == react_hex
        except:
            return None
    
    def _get_pickable_players_str(self):
        players = ""
        for react_hex, player in self.react_player_picks.items():
            react = self._get_pick_reaction(int(react_hex, base=16))
            players += "{} {}\n".format(react, player.mention)
        return players

    async def update_game_info(self, helper_role=None, invalid=False, prefix='?'):
        if not helper_role:
            helper_role = self.helper_role
        sm_title = "{0} {1} Mans Game Info".format(self.queue.name, self.queue.queueMaxSize)
        embed_color = discord.Colour.green()
        if invalid:
            sm_title += " :x: [Teams Changed]"
            embed_color = discord.Colour.red()
        embed = discord.Embed(title=sm_title, color=embed_color)
        embed.set_thumbnail(url=self.queue.guild.icon_url)

        if self.queue.teamSelection == Strings.VOTE_TS:
            ts_emoji = self._get_ts_emoji()
            team_selection = self.teamSelection
            if team_selection == Strings.BALANCED_TS:
                try:
                    team_selection += "\n\nBalance Score: {}".format(round(self.balance_score/2, 2))
                    team_selection += "\n_Lower Balance Scores = More Balanced_"
                except:
                    pass 
            embed.add_field(name="Team Selection", value="{} {}".format(ts_emoji, team_selection), inline=False)
        embed.add_field(name="Blue Team", value="{}\n".format(", ".join([player.mention for player in self.blue])), inline=False)
        embed.add_field(name="Orange Team", value="{}\n".format(", ".join([player.mention for player in self.orange])), inline=False)
        if not invalid:
            embed.add_field(name="Captains", value="**Blue:** {0}\n**Orange:** {1}".format(self.captains[0].mention, self.captains[1].mention), inline=False)
        embed.add_field(name="Lobby Info", value="**Name:** {0}\n**Password:** {1}".format(self.roomName, self.roomPass), inline=False)
        embed.add_field(name="Point Breakdown", value="**Playing:** {0}\n**Winning Bonus:** {1}"
            .format(self.queue.points[Strings.PP_PLAY_KEY], self.queue.points[Strings.PP_WIN_KEY]), inline=False)
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
        embed.set_footer(text="Game ID: {}".format(self.id))
        
        self.info_message = await self.textChannel.send(embed=embed)
        # await self._notify(new_state=Strings.ONGOING_GS)

# General Helper Commands
    def _get_ts_emoji(self):
        for key, value in SELECTION_MODES.items():
            if value == self.teamSelection:
                return self._get_pick_reaction(key)

    def reset_players(self):
        self.players.update(self.orange)
        self.players.update(self.blue)

    def get_new_captains_from_teams(self):
        self.captains = []
        self.captains.append(random.sample(list(self.blue), 1)[0])
        self.captains.append(random.sample(list(self.orange), 1)[0])

    def _generate_name_pass(self):
        return Strings.room_pass[random.randrange(len(Strings.room_pass))]

    async def _add_reactions(self, react_hex_codes, message):
        for react_hex_i in react_hex_codes:
            if type(react_hex_i) == int:
                react = struct.pack('<I', react_hex_i).decode('utf-32le')
                await message.add_reaction(react)
            elif type(react_hex_i) == str:
                react = struct.pack('<I', int(react_hex_i, base=16)).decode('utf-32le')
                await message.add_reaction(react)

    def _get_wp(self, wins, losses):
        try:
            return wins/(wins+losses)
        except ZeroDivisionError:
            return None

    def _get_completion_color(self, voted:int, pending:int):
        if not (voted or pending):
            return discord.Color.default()
        red = (255, 0, 0)
        yellow = (255, 255, 0)
        green = (0, 255, 0)
        wp = self._get_wp(voted, pending)
        
        if wp == 0:
            return discord.Color.from_rgb(*red)
        if wp == 0.5:
            return discord.Color.from_rgb(*yellow)
        if wp == 1:
            return discord.Color.from_rgb(*green)
        
        blue_scale = 0
        if wp < 0.5:
            wp_adj = wp/0.5
            red_scale = 255
            green_scale = round(255*wp_adj)
            return discord.Color.from_rgb(red_scale, green_scale, blue_scale)
        else:
            #sub_wp = ((wp-50)/50)*100
            wp_adj = (wp-0.5)/0.5
            green_scale = 255
            red_scale = 255 - round(255*wp_adj)
            return discord.Color.from_rgb(red_scale, green_scale, blue_scale)
            
    def __contains__(self, item):
        return item in self.players or item in self.orange or item in self.blue

    def _to_dict(self):
        info_msg = self.info_message.id if self.info_message else None
        txt_channel = self.textChannel.id if self.textChannel else None
        try:
            vc_channels = [x.id for x in self.voiceChannels]
        except:
            vc_channels = None

        game_dict = {
            "Players": [x.id for x in self.players],
            "Captains": [x.id for x in self.captains],
            "Blue": [x.id for x in self.blue],
            "Orange": [x.id for x in self.orange],
            "RoomName": self.roomName,
            "RoomPass": self.roomPass,
            "TextChannel": txt_channel,
            "VoiceChannels": vc_channels,
            "QueueId": self.queue.id,
            "ScoreReported": self.scoreReported,
            "HelperRole": self.helper_role.id,
            "TeamSelection": self.teamSelection,
            "InfoMessage": info_msg,
            "State": self.game_state
        }

        return game_dict
