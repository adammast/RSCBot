from sys import prefix
from turtle import pd
from typing import NewType
import discord
import re
import ast
import asyncio
import difflib

from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
from collections import Counter
from redbot.core.utils.predicates import MessagePredicate
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions
from discord.ext.commands import Context

import requests
from teamManager import TeamManager


defaults = {"BaseUrl": None, "LeagueHeader": None}
verify_timeout = 30

DONE = "Done"

class StatsManager(commands.Cog):
    """Enables access to Player and Team Stats"""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567892, force_registration=True)
        self.config.register_guild(**defaults)
        self.team_manager : TeamManager = bot.get_cog("TeamManager")

        asyncio.create_task(self._pre_load_data())

# region Admin Commands
    @commands.command(aliases=['setURL', 'seturl'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def setUrl(self, ctx: Context, base_url: str):
        if 'https://' not in base_url:
            base_url = f"https://{base_url}"
        await self._save_url(ctx.guild, base_url)
        await ctx.send(DONE)
    
    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def setLeagueHeader(self, ctx: Context, league_header: str):
        await self._save_url(ctx.guild, league_header)
        await ctx.send(DONE)

# endregion

# region General Commands
    @commands.command(aliases=['setURL', 'seturl'])
    @commands.guild_only()
    async def playerStats(self, ctx, player: discord.Member=None):
        if not player:
            player = ctx.author
        
        team = (await self.team_manager.teams_for_user(ctx, player))[0]
        stats = await self.get_player_stats(ctx.guild, player, team)
        embed = self.get_player_stats_embed(ctx, player, stats)

        await ctx.send(embed=embed)

# endregion

# region Helper Commands
    async def _pre_load_data(self):
        await self.bot.wait_until_ready()
        self.base_urls = {}
        self.league_headers = {}

        for guild in self.bot.guilds:
            self.base_urls[guild] = await self.get_url(guild)
            self.league_headers[guild] = await self.get_league_header(guild)
    
    async def get_player_stats(self, guild: discord.Guild, player: discord.Member, team: str):
        if not self.base_urls.get(guild, False):
            return None
        
        full_url = f"{self.base_urls[guild]}/players/{team}"
        
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(
            None, lambda: requests.get(
                full_url,
                headers={'League': self.league_headers[guild]}
            )
        )
        response = await future

        data = response.json()

        player_name = self.get_name_components(player)[1]
        player_data = {}
        for p_data in data:
            if p_data.get('playerName', '') == player_name:
                player_data = p_data
                break

        return player_data
    
    async def get_player_stats_embed(self, ctx, player, team, stats):
        player_name = self.get_name_components(player)[1]
        franchise_role, tier_role = await self.team_manager._roles_for_team(ctx, team)

        embed = discord.Embed(title=f"{player_name} Player Stats", color=tier_role.color)

        emoji = await self.team_manager._get_franchise_emoji(ctx, franchise_role)
        if emoji:
            embed.set_thumbnail(url=emoji.url)
        else:
            embed.set_thumbnail(url=ctx.guild.icon_url)
        
        include_stats = ["GP", "GW", "GL", "wPct", "pts", "goals", "assists", "saves", "shots", "shotPct", "ppg", "cycles", "hatTricks", "playmakers", "saviors"]
        for stat in include_stats:
            stat_title = self.get_stat_title(stat)
            embed.add_field(name=stat_title, value=stats.get(include_stats, "N/A")) # , inline=False)
        
        return embed
    
    def get_stat_title(self, stat_code):
        stat_code_titles = {
            "gp": "GP",
            "hattricks": "Hat Tricks",
            "playmakers": "Play Makers",
            "goals": "Goals",
            "assists": "Assists",
            "shots": "Shots",
            "cycles": "Cycles"
        }
        return stat_code_titles.get(stat_code.lower(), stat_code)

    def get_name_components(self, member: discord.Member):
        if member.nick:
            name = member.nick
        else:
            return "", member.name, ""
        prefix = name[0:name.index(' | ')] if ' | ' in name else ''
        if prefix:
            name = name[name.index(' | ')+3:]
        player_name = ""
        awards = ""
        for char in name[::-1]:
            if char not in self.LEAGUE_AWARDS:
                break
            awards = char + awards

        player_name = name.replace(" " + awards, "") if awards else name

        return prefix.strip(), player_name.strip(), awards.strip()

# endregion 

# region JSON
    async def _save_url(self, guild: discord.Guild, url):
        await self.config.guild(guild).BaseUrl.set(url)
        self.base_urls[guild] = url

    async def get_url(self, guild: discord.Guild):
        return await self.config.guild(guild).BaseUrl()

    async def _save_league_header(self, guild: discord.Guild, league_header):
        await self.config.guild(guild).LeagueHeader.set(league_header)
        self.league_headers[guild] = league_header

    async def get_league_header(self, guild: discord.Guild):
        return await self.config.guild(guild).LeagueHeader()
       
# endregion
