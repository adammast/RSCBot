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

        tier_data = self._tier_data(ctx, match_day, tier)
        if user not in tier_data:
            await self._send_register_message(ctx, user, match_day, tier)
        else:
            await self._send_unregister_message(ctx, user, match_day, tier)

        await self.bot.delete_message(ctx.message)

    @commands.command(pass_context=True, no_pm=True, aliases=["ca"])
    async def checkAvailability(self, ctx, tier: str, match_day: int = None):
        if match_day is None:
            match_day = self.match_cog._match_day(ctx)
        tier_list = self._tier_data(ctx, match_day, tier)
        message = "```Availability for {0} tier on match day {1}:".format(tier, match_day)
        for fa in tier_list:
            message += "\n\t{0}".format(fa.nick)
        message += "```"
        await self.bot.say(message)

    async def _send_register_message(self, ctx, user, match_day, tier):
        embed = discord.Embed(title="Register Availability", 
            description="By registering your availability you are letting GMs know that you are available to play "
                "on the following match day in the following tier. To confirm react with 👍",
            colour=discord.Colour.blue())
        embed.add_field(name="Match Day", value=match_day, inline=True)
        embed.add_field(name="Tier", value=tier, inline=True)
        message = await self.bot.send_message(user, embed=embed)

        await self.bot.add_reaction(message, '👍')

        def check(reaction, user):
            return str(reaction.emoji) == '👍'

        try:
            result = await self.bot.wait_for_reaction(message=message, timeout=30.0, check=check, user=user)
        except:
            await self.bot.send_message(user, "Sorry, you either didn't react quick enough or something went wrong. Please try again.")
            return

        if result:
            self._register_user(ctx, user, match_day, tier)
            await self.bot.send_message(user, "Thank you for registering! GMs will now be able to see that you're available.")
        else:
            await self.bot.send_message(user, "Sorry, you didn't react quick enough. Please try again.")

    async def _send_unregister_message(self, ctx, user, match_day, tier):
        embed = discord.Embed(title="Register Availability", 
            description="You have alreayd marked your availability for the following match day and tier. "
                "Do you wish to take yourself off the availability list? To confirm you want to unregister, react with 👎",
            colour=discord.Colour.blue())
        embed.add_field(name="Match Day", value=match_day, inline=True)
        embed.add_field(name="Tier", value=tier, inline=True)
        message = await self.bot.send_message(user, embed=embed)

        await self.bot.add_reaction(message, '👎')

        def check(reaction, user):
            return str(reaction.emoji) == '👎'

        try:
            result = await self.bot.wait_for_reaction(message=message, timeout=30.0, check=check, user=user)
        except:
            await self.bot.send_message(user, "Sorry, you either didn't react quick enough or something went wrong. Please try again.")
            return

        if result:
            self._unregister_user(ctx, user, match_day, tier)
            await self.bot.send_message(user, "You have been removed from the list. Thank you for updating your availability!")
        else:
            await self.bot.send_message(user, "Sorry, you didn't react quick enough. Please try again.")

    def _register_user(self, ctx, user, match_day, tier):
        tier_list = self._tier_data(ctx, match_day, tier)
        tier_list.append(user)
        self._save_data(ctx, match_day, tier, tier_list)

    def _unregister_user(self, ctx, user, match_day, tier):
        tier_list = self._tier_data(ctx, match_day, tier)
        tier_list.remove(user)
        self._save_data(ctx, match_day, tier, tier_list)

    def _find_tier_from_fa_role(self, ctx, user: discord.Member):
        tiers = self.team_manager_cog._tiers(ctx)
        for tier in tiers:
            fa_role = self.team_manager_cog._find_role_by_name(ctx, tier + "FA")
            if fa_role in user.roles:
                return tier
        return None

    def _save_data(self, ctx, match_day, tier, tier_data):
        all_data = self._all_data(ctx)
        match_data = all_data.setdefault(match_day, {})
        match_data[tier] = tier_data
        self.data_cog._save_data(ctx, self.DATASET, all_data)

    def _tier_data(self, ctx, match_day, tier):
        match_data = self._match_data(ctx, match_day)
        tier_data = match_data.setdefault(tier, [])
        return tier_data

    def _match_data(self, ctx, match_day):
        all_data = self._all_data(ctx)
        match_data = all_data.setdefault(match_day, {})
        return match_data

    def _all_data(self, ctx):
        all_data = self.data_cog.load(ctx, self.DATASET)
        return all_data

def setup(bot):
    bot.add_cog(FaRegister(bot))