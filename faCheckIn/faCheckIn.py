import discord
import asyncio
import difflib

from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
from redbot.core.utils.predicates import MessagePredicate
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions

defaults = {"CheckIns": {}}
verify_timeout = 30

class FaCheckIn(commands.Cog):

    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567894, force_registration=True)
        self.config.register_guild(**defaults)
        self.team_manager_cog = bot.get_cog("TeamManager")
        self.match_cog = bot.get_cog("Match")

    @commands.guild_only()
    @commands.command(aliases=["ci"])
    async def checkIn(self, ctx):
        user = ctx.message.author
        match_day = await self.match_cog._match_day(ctx)
        tier = await self._find_tier_from_fa_role(ctx, user)

        await ctx.message.delete()

        if tier is not None:
            tier_data = await self._tier_data(ctx, match_day, tier)
            if user.id not in tier_data:
                await self._send_check_in_message(ctx, user, match_day, tier)
            else:
                await user.send("You've already checked in. If you want to check out, use the `{0}checkOut` command.".format(ctx.prefix))
        else:
            await user.send("Only free agents are allowed to check in. If you are a free agent and are unable to check in please message an admin.")

    @commands.guild_only()
    @commands.command(aliases=["co"])
    async def checkOut(self, ctx):
        user = ctx.message.author
        match_day = await self.match_cog._match_day(ctx)
        tier = await self._find_tier_from_fa_role(ctx, user)
        if tier is None:
            tier = await self.team_manager_cog.get_current_tier_role(ctx, user)

        await ctx.message.delete()

        if tier is not None:
            tier_data = await self._tier_data(ctx, match_day, tier)
            if user.id in tier_data:
                await self._send_check_out_message(ctx, user, match_day, tier)
            else:
                await user.send("You aren't currently checked in. If you want to check in, use the `{0}checkIn` command.".format(ctx.prefix))
        else:
            await user.send("Your tier could not be determined. If you are in the league please contact an admin for help.")

    @commands.guild_only()
    @commands.command(aliases=["ca"])
    async def checkAvailability(self, ctx, tier_name: str, match_day: str = None):
        if match_day is None:
            match_day = await self.match_cog._match_day(ctx)
        tier = await self.team_manager_cog._match_tier_name(ctx, tier_name)
        if tier is None:
            await ctx.send("No tier with name: `{0}`".format(tier_name))
            return

        tier_list = await self._tier_data(ctx, match_day, tier)
        perm_fa_role = self.team_manager_cog._find_role_by_name(ctx, self.team_manager_cog.PERM_FA_ROLE)

        message = "```Availability for {0} tier on match day {1}:".format(tier, match_day)
        await ctx.send("{}".format(tier_list))
        for user in tier_list:
            member = await commands.MemberConverter().convert(ctx, user)
            if member in ctx.message.guild.members:
                if await self._find_tier_from_fa_role(ctx, member) is not None:
                    message += "\n\t{0}".format(member.nick)
                    if perm_fa_role is not None and perm_fa_role in member.roles:
                        message += " (Permanent FA)"
        message += "```"
        await ctx.send(message)

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearAvailability(self, ctx, tier: str = None, match_day: str = None):
        if match_day is None:
            match_day = await self.match_cog._match_day(ctx)

        if tier is None:
            await self._save_match_data(ctx, match_day, {})
        else:
            await self._save_tier_data(ctx, match_day, tier, [])
        await ctx.send("Done.")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearAllAvailability(self, ctx):
        self._save_data(ctx, {})
        await ctx.send("Done.")

    async def _send_check_in_message(self, ctx, user, match_day, tier):
        embed = discord.Embed(title="Check In", 
            description="By checking in you are letting GMs know that you are available to play "
                "on the following match day in the following tier. To confirm react with {}".format(ReactionPredicate.YES_OR_NO_EMOJIS[0]),
            colour=discord.Colour.blue())
        embed.add_field(name="Match Day", value=match_day, inline=True)
        embed.add_field(name="Tier", value=tier, inline=True)

        react_msg = await user.send(embed=embed)
        start_adding_reactions(react_msg, ReactionPredicate.YES_OR_NO_EMOJIS)

        try:
            pred = ReactionPredicate.yes_or_no(react_msg, user)
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=verify_timeout)
            if pred.result is True:
                await self._register_user(ctx, user, match_day, tier)
                await user.send("Thank you for checking in! GMs will now be able to see that you're available.")
            else:
                await user.send("Not checked in. If you wish to check in use the command again.")
        except asyncio.TimeoutError:
            await user.send("Sorry, you didn't react quick enough. Please try again.")

    async def _send_check_out_message(self, ctx, user, match_day, tier):
        embed = discord.Embed(title="Check Out", 
            description="You are currently checked in as available for the following match day and tier. "
                "Do you wish to take yourself off the availability list? To confirm you want to check out, react with 👎",
            colour=discord.Colour.blue())
        embed.add_field(name="Match Day", value=match_day, inline=True)
        embed.add_field(name="Tier", value=tier, inline=True)

        react_msg = await user.send(embed=embed)
        start_adding_reactions(react_msg, ReactionPredicate.YES_OR_NO_EMOJIS)

        try:
            pred = ReactionPredicate.yes_or_no(react_msg, user)
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=verify_timeout)
            if pred.result is True:
                await self._unregister_user(ctx, user, match_day, tier)
                await user.send("You have been removed from the list. Thank you for updating your availability!")
            else:
                await user.send("Still checked in. If you wish to check out use the command again.")
        except asyncio.TimeoutError:
            await user.send("Sorry, you didn't react quick enough. Please try again.")

    async def _register_user(self, ctx, user, match_day, tier):
        tier_list = await self._tier_data(ctx, match_day, tier)
        tier_list.append(user.id)
        await self._save_tier_data(ctx, match_day, tier, tier_list)

    async def _unregister_user(self, ctx, user, match_day, tier):
        tier_list = await self._tier_data(ctx, match_day, tier)
        tier_list.remove(user.id)
        await self._save_tier_data(ctx, match_day, tier, tier_list)

    async def _find_tier_from_fa_role(self, ctx, user: discord.Member):
        tiers = await self.team_manager_cog._tiers(ctx)
        for tier in tiers:
            fa_role = self.team_manager_cog._find_role_by_name(ctx, tier + "FA")
            if fa_role in user.roles:
                return tier
        return None

    async def _save_tier_data(self, ctx, match_day, tier, tier_data):
        check_ins = await self._check_ins(ctx)
        match_data = check_ins.setdefault(match_day, {})
        match_data[tier] = tier_data
        await self._save_check_ins(ctx, check_ins)

    async def _save_match_data(self, ctx, match_day, match_data):
        check_ins = await self._check_ins(ctx)
        check_ins[match_day] = match_data
        await self._save_check_ins(ctx, check_ins)

    async def _tier_data(self, ctx, match_day, tier):
        match_data = await self._match_data(ctx, match_day)
        tier_data = match_data.setdefault(tier, [])
        return tier_data

    async def _match_data(self, ctx, match_day):
        check_ins = await self._check_ins(ctx)
        match_data = check_ins.setdefault(match_day, {})
        return match_data

    async def _check_ins(self, ctx):
        return await self.config.guild(ctx.guild).CheckIns()

    async def _save_check_ins(self, ctx, check_ins):
        await self.config.guild(ctx.guild).CheckIns.set(check_ins)