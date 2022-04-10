import discord
import asyncio

from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
from discord.ext.commands import Context

import requests
from urllib.parse import quote as encodeurl
from teamManager import TeamManager
from .statsReference import StatsReference as sr

defaults = {"BaseUrl": None, "LeagueHeader": None}
verify_timeout = 30

class StatsManager(commands.Cog):
    """Enables access to Player and Team Stats"""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567892, force_registration=True)
        self.config.register_guild(**defaults)
        self.team_manager : TeamManager = bot.get_cog("TeamManager")

        asyncio.create_task(self._pre_load_data())

# region Admin Commands
    @commands.command(aliases=['setStatsURL', 'setstatsurl'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def setStatsUrl(self, ctx: Context, base_url: str):
        """Sets url for stats retrieval. Do not include "https://" or closing slashes (/).
        
        Example:
        [p]setStatsUrl api.rscstream.com
        """
        if base_url[:8] == "https://":
            base_url = base_url[8:]
        await self._save_url(ctx.guild, base_url)
        await ctx.send(sr.DONE)
    
    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def setLeagueHeader(self, ctx: Context, league_header: str):
        """Sets "League" request header. This is used to enable stats for non-standard
        Leagues such as 2v2
        
        Example:
        [p]setLeagueHeader twos
        """
        await self._save_league_header(ctx.guild, league_header)
        await ctx.send(sr.DONE)

# endregion

# region General Commands
    @commands.command(aliases=['ts', 'teamStatsCard', 'tsc'])
    @commands.guild_only()
    async def teamStats(self, ctx, *, team_name: str):
        """Retrieves Team Stats for the current season"""
        team, found = await self.team_manager._match_team_name(ctx, team_name)
        if found:
            try:
                franchise_role, tier_role = await self.team_manager._roles_for_team(ctx, team)
            except LookupError:
                return await ctx.send(f":x: No team found with name {team}")

            stats = await self.get_team_stats(ctx.guild, team, tier_role.name)

            # if not stats:
            #     return await ctx.send(f":x: No stats found for **{player.nick}**")
            embed = await self.get_team_stats_embed(ctx, team, franchise_role, tier_role, stats)
            await ctx.send(embed=embed)
        else:
            possible_teams = team
            all_teams = await self.team_manager._teams(ctx)
            message = "No team with name: {0}".format(team_name)
            if possible_teams:
                message += "\nDo you mean one of these teams:"
                for possible_team in possible_teams:
                    message += " `{0}`".format(possible_team)
            await ctx.send(message)

    @commands.command(aliases=['ps', 'statsCard', 'sc', 'psc'])
    @commands.guild_only()
    async def playerStats(self, ctx, *, player: discord.Member=None):
        """Retrieves Player Stats for the current season"""
        if not player:
            player = ctx.author
        
        if sr.LEAGUE_ROLE_NAME not in [role.name for role in player.roles]:
            return await ctx.send(":x: This command is only supported for active players.")
            
        team = await self.team_manager.get_current_team_name(ctx, player)
        stats = await self.get_player_stats(ctx.guild, player, team)

        # if not stats:
        #     return await ctx.send(f":x: No stats found for **{player.nick}**")
        embed = await self.get_player_stats_embed(ctx, player, team, stats)
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
                f"https://{encodeurl(full_url)}",
                headers={'League': self.league_headers[guild]}
            )
        )
        response = await future

        data = response.json()

        # from pprint import pprint as pp
        # pp(data)

        player_name = self.get_name_components(player)[1]

        for player_data in data:
            if player_data.get('playerName', '') == player_name:
                return player_data

        return {}
    
    async def get_team_stats(self, guild: discord.Guild, team: str, tier: str):
        if not self.base_urls.get(guild, False):
            return None
        
        full_url = f"{self.base_urls[guild]}/teams/{tier}"
        
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(
            None, lambda: requests.get(
                f"https://{encodeurl(full_url)}",
                headers={'League': self.league_headers[guild]}
            )
        )
        response = await future

        data = response.json()

        # from pprint import pprint as pp
        # pp(data)
        for team_data in data:
            if team_data.get('teamName', '') == team:
                return team_data

        return {}
    
    # async def team_gm_match(self, ctx, player: discord.Member):
    #     return await self.team_manager.get_current_team_name(ctx, player)

    def get_code_title(self, code):
        return sr.DATA_CODE_NAME_MAP.get(code.lower(), code)

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
            if char not in sr.LEAGUE_AWARDS:
                break
            awards = char + awards

        player_name = name.replace(" " + awards, "") if awards else name

        return prefix.strip(), player_name.strip(), awards.strip()

# endregion

# region Embeds
    async def get_player_stats_embed(self, ctx, player, team, player_stats):
        under_contract = bool(team)
        player_name = self.get_name_components(player)[1]
        player_name = player_name.replace(player_name[0], player_name[0].upper())
        
        if under_contract:
            franchise_role, tier_role = await self.team_manager._roles_for_team(ctx, team)
            emoji = await self.team_manager._get_franchise_emoji(ctx, franchise_role)
        else:
            tier_role = await self.team_manager.get_current_tier_role(ctx, player)
            emoji = None

        embed = discord.Embed(title=f"{player_name}'s Player Stats Card", color=tier_role.color)

        if emoji:
            embed.set_thumbnail(url=emoji.url)
        else:
            embed.set_thumbnail(url=ctx.guild.icon_url)
        
        team_info = ""
        team_info += f"**Tier:** {tier_role.mention}"

        if under_contract:
            team_info += f"\n**Franchise:** {franchise_role.name}"
            team_info += f"\n**Team:** {team}"
        else:
            contract =  "Permanent Free Agent" if sr.PERM_FA_ROLE_NAME in [role.name for role in player.roles] else "Free Agent"
            team_info += f"\n**Contract:** {contract}"
        
        embed.add_field(name="Team Info", value=team_info, inline=False)

        if under_contract:
            if player_stats:
                for stat in sr.INCLUDE_PLAYER_STATS:
                    stat_title = self.get_code_title(stat)
                    embed.add_field(name=stat_title, value=player_stats.get(stat, "N/A")) # , inline=False)
            else:
                embed.add_field(name="No Stats, Sorry!", value=sr.NO_STATS_FOUND_MSG)
        else:
            embed.add_field(name="No Stats, Sorry!", value=sr.NO_FA_STATS_MSG)

        return embed
    
    async def get_team_stats_embed(self, ctx, team, franchise_role: discord.Role, tier_role: discord.Role, team_stats):
        
        embed = discord.Embed(title=f"{team}'s Team Stats", color=tier_role.color)

        emoji = await self.team_manager._get_franchise_emoji(ctx, franchise_role)
        if emoji:
            embed.set_thumbnail(url=emoji.url)
        else:
            embed.set_thumbnail(url=ctx.guild.icon_url)
        
        # Team Info
        team_info = f"**Tier:** {tier_role.mention}"
        for tli in sr.TEAM_LEAGUE_INFO:
            info = team_stats.get(tli)

            if info:
                if tli.lower() == "gm":
                    team_info += f"\n**{tli.upper()}**: {info}"
                else:
                    team_info += f"\n**{tli.title()}**: {info}"
            
        embed.add_field(name="Team Info", value=team_info, inline=False)

        # Current Roster
        roster = self.team_manager.members_from_team(ctx, franchise_role, tier_role)
        roster_str = "```\n{}\n```".format('\n'.join(player.nick for player in roster))
        embed.add_field(name="Current Roster", value=roster_str, inline=False)

        # Stats
        for stat in sr.INCLUDE_TEAM_STATS:
            stat_title = self.get_code_title(stat)
            embed.add_field(name=stat_title, value=team_stats.get(stat, "N/A")) # , inline=False)

        return embed
    
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
