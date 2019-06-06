import discord
import asyncio
import datetime

from discord.ext import commands

class FaRegister:

    DATASET = "FaCheckInData"

    def __init__(self, bot):
        self.bot = bot
        self.data_cog = self.bot.get_cog("RscData")
        self.team_manager_cog = self.bot.get_cog("TeamManager")
        self.match_cog = self.bot.get_cog("Match")

    @commands.command(pass_context=True, no_pm=True, aliases=["ra"])
    async def registerAvailability(self, ctx):
        user = ctx.message.author
        match_day = self.match_cog._match_day(ctx)
        tier = self._find_tier_from_fa_role(ctx, user)

        embed = discord.Embed(title="Register Availability", 
            description="By registering your availability you are letting GMs know that you are available to play on the following match day in the following tier. To confirm react with 👍 ",
            colour=discord.Colour.blue())
        embed.add_field(name="Match Day", value=match_day, inline=True)
        embed.add_field(name="Tier", value=tier, inline=True)
        message = await self.bot.send_message(user, embed=embed)

        await self.bot.add_reaction(message, '👍')

        def check(reaction, user):
            return str(reaction.emoji) == '👍'

        try:
            await self.bot.wait_for_reaction(message=message, timeout=30.0, check=check, user=user)
        except asyncio.TimeoutError:
            await self.bot.send_message(user, "Sorry, you took too long to respond. Please try again.")
            return
            
        await self.bot.send_message(user, "Thank you for registering!")

    def _find_tier_from_fa_role(self, ctx, user: discord.Member):
        tiers = self.team_manager_cog._tiers(ctx)
        for tier in tiers:
            fa_role = self.team_manager_cog._find_role_by_name(ctx, tier + "FA")
            if fa_role in user.roles:
                return tier
        return None

    def _all_data(self, ctx):
        all_data = self.data_cog.load(ctx, self.DATASET)
        return all_data

def setup(bot):
    bot.add_cog(FaRegister(bot))