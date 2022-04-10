from sys import prefix
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


defaults = {"url": None}
verify_timeout = 30


class StatsManager(commands.Cog):
    """Enables access to Player and Team Stats"""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567892, force_registration=True)
        self.config.register_guild(**defaults)
        self.prefix_cog = bot.get_cog("TeamManager")

# region Admin Commands
    @commands.command(aliases=['setURL', 'seturl'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def setUrl(self, ctx, tier_name: str):
        pass 

# region General Commands

# JSON

