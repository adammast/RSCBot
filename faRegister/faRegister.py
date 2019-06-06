import discord
import asyncio

from discord.ext import commands

class FaRegister:

    DATASET = "FaCheckInData"

    def __init__(self, bot):
        self.bot = bot
        self.data_cog = self.bot.get_cog("RscData")
        self.team_manager_cog = self.bot.get_cog("TeamManager")
        self.match_cog = self.bot.get_cog("Match")

    @commands.bot.event
    @commands.command(pass_context=True, no_pm=True, aliases=["ra"])
    async def registerAvailability(self, ctx):
        user = ctx.message.author
        match_day = self.match_cog._match_day(ctx)
        tier = self._find_tier_from_fa_role(ctx, user)

        message = await self.bot.send_message(user, "By registering your availability you are letting GMs know "
            "that you are active to play on the following match day in the following tier: "
            "\n\t**Match Day:** `{0}`"
            "\n\t**Tier:** `{1}`"
            "\n\nIf this information is correct please press the 👍 reaction below.".format(match_day, tier))

        await self.bot.add_reaction(message, '👍')

        def check(reaction, user):
            return user == ctx.message.author and str(reaction.emoji) == '👍'

        try:
            await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
        except asyncio.TimeoutError:
            await self.bot.send_message(user, "Sorry, you took too long to respond. Please try again.")
        else:
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