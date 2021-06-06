import random
import struct
import uuid

import discord

from .config import config
from .queue import SixMansQueue


class Game:
    def __init__(
            self, players, queue: SixMansQueue,
            guild: discord.Guild=None,
            category=None,
            helper_role=None,
            automove=False,
            text_channel: discord.TextChannel=None, 
            voice_channels=None,
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
        self.game_state = "team selection"
        
        # Optional params
        self.guild = guild
        self.category = category
        self.helper_role = helper_role
        self.automove = automove
        self.observers = observers if observers else []

        self.teams_message = None
        if text_channel and voice_channels:
            self.textChannel = text_channel
            self.voiceChannels = voice_channels #List of voice channels: [Blue, Orange]
        else:
            self.textChannel = None
            self.voiceChannels = None

        # attatch listeners to game
        for observer in self.observers:
            observer._subject = self
    
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

    async def create_game_channels(self, six_mans_queue, category=None):
        # sync permissions on channel creation, and edit overwrites (@everyone) immediately after
        code = str(self.id)[-3:]
        self.textChannel = await self.guild.create_text_channel(
            "{} {} 6 Mans".format(code, six_mans_queue.name), 
            permissions_synced=True,
            category=category
        )
        await self.textChannel.set_permissions(self.guild.default_role, view_channel=False, read_messages=False)
        for player in self.players:
            await self.textChannel.set_permissions(player, read_messages=True)
        blue_vc = await self.guild.create_voice_channel("{} | {} Blue Team".format(code, six_mans_queue.name), permissions_synced=True, category=category)
        await blue_vc.set_permissions(self.guild.default_role, connect=False)
        oran_vc = await self.guild.create_voice_channel("{} | {} Orange Team".format(code, six_mans_queue.name), permissions_synced=True, category=category)
        await oran_vc.set_permissions(self.guild.default_role, connect=False)
        
        # manually add helper role perms if there is not an associated 6mans category
        if self.helper_role and not category:
            await self.textChannel.set_permissions(self.helper_role, view_channel=True, read_messages=True)
            await blue_vc.set_permissions(self.helper_role, connect=True)
            await oran_vc.set_permissions(self.helper_role, connect=True)
        
        self.voiceChannels = [blue_vc, oran_vc]

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

    async def pick_random_teams(self):
        await self.shuffle_players()
        await self._notify(new_state="ongoing")

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

    async def captains_pick_teams(self, helper_role):
        # Mentions all players
        await self.textChannel.send(', '.join(player.mention for player in self.players))
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
        self.teams_message = await self.textChannel.send(embed=embed)
        
        for react_hex in self.react_player_picks.keys():
            react = struct.pack('<I', int(react_hex, base=16)).decode('utf-32le')
            await self.teams_message.add_reaction(react)

    async def process_captains_pick(self, reaction, user):
        teams_complete = False
        pick_i = len(self.blue)+len(self.orange)-2
        pick_order = ['blue', 'orange', 'orange', 'blue']
        pick = pick_order[pick_i]
        captain_picking = self.captains[0] if pick == 'blue' else self.captains[1]
        
        if user != captain_picking and user.id != 302079469882179585:
            return False
        
        # get player from reaction
        player_picked = self._get_player_from_reaction_emoji(ord(reaction.emoji))
        await self.teams_message.clear_reaction(reaction.emoji)
        
        # add to correct team, update teams embed
        self.blue.add(player_picked) if pick == 'blue' else self.orange.add(player_picked)
        
        # TODO: automatically process last pick
        picks_remaining = list(self.react_player_picks.keys())
        if len(picks_remaining) > 1:
            embed = self._get_captains_embed(pick_order[pick_i+1])
            await self.teams_message.edit(embed=embed)
        
        elif len(picks_remaining) == 1:
            last_pick = 'blue' if len(self.orange) > len(self.blue) else 'orange'
            last_pick_key = picks_remaining[0]
            last_player = self.react_player_picks[last_pick_key]
            del self.react_player_picks[last_pick_key]
            await self.teams_message.clear_reactions()
            self.blue.add(last_player) if last_pick == 'blue' else self.orange.add(last_player)
            teams_complete = True
            embed = self._get_captains_embed(None, guild=last_player.guild)
            await self.teams_message.edit(embed=embed)
        
        if teams_complete:
            for player in self.blue:
                await self.add_to_blue(player)
            for player in self.orange:
                await self.add_to_orange(player)
            self.reset_players()
        
        await self._notify(new_state="ongoing")
        return teams_complete

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
      
    async def report_winner(self, winner):
        await self.color_embed_for_winners(winner)
        await self._notify(new_state="game over")

    async def color_embed_for_winners(self, winner):
        winner = winner.lower()
        if winner == 'blue':
            color = discord.Colour.blue()
        elif winner == 'orange':
            color = discord.Colour.orange()
        else:
            color = discord.Colour.green()  # catch all for errors hopefully

        embed = self.teams_message.embeds[0]
        embed_dict = embed.to_dict()
        embed_dict['color'] = color.value
        embed = discord.Embed.from_dict(embed_dict)
        await self.teams_message.edit(embed=embed)

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

    async def pick_balanced_teams(self):
        pass

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
            "QueueId": self.queue.id,
            "ScoreReported": self.scoreReported,
        }

    def _generate_name_pass(self):
        return config.room_pass[random.randrange(len(config.room_pass))]
