import asyncio

import discord
from discord.ext.commands import Context
from match import Match
from redbot.core import Config, checks, commands
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate
from teamManager import TeamManager

VERIFY_TIMEOUT = 30

defaults = {"CheckIns": {}}

class FaCheckIn(commands.Cog):

    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567894, force_registration=True)
        self.config.register_guild(**defaults)
        self.team_manager_cog: TeamManager = bot.get_cog("TeamManager")
        self.match_cog: Match = bot.get_cog("Match")

#region commands

    @commands.guild_only()
    @commands.command(aliases=["ci"])
    async def checkIn(self, ctx: Context):
        member: discord.Member = ctx.author
        match_day = await self.match_cog._match_day(ctx.guild)
        tier = await self.find_tier_from_fa_role(ctx, member)

        await ctx.message.delete()

        if tier is not None:
            tier_data = await self._tier_data(ctx.guild, match_day, tier)
            if member.id not in tier_data:
                await self.send_check_in_message(ctx, member, match_day, tier)
            else:
                await member.send("You've already checked in. If you want to check out, use the `{0}checkOut` command.".format(ctx.prefix))
        else:
            await member.send("Only free agents are allowed to check in. If you are a free agent and are unable to check in please message an admin.")

    @commands.guild_only()
    @commands.command(aliases=["co"])
    async def checkOut(self, ctx: Context):
        member: discord.Member = ctx.author
        match_day = await self.match_cog._match_day(ctx)
        tier = await self.find_tier_from_fa_role(ctx, member)
        if tier is None:
            tier = await self.team_manager_cog.get_current_tier_role(ctx, member)

        await ctx.message.delete()

        if tier is not None:
            tier_data = await self._tier_data(ctx.guild, match_day, tier)
            if member.id in tier_data:
                await self.send_check_out_message(ctx, member, match_day, tier)
            else:
                await member.send("You aren't currently checked in. If you want to check in, use the `{0}checkIn` command.".format(ctx.prefix))
        else:
            await member.send("Your tier could not be determined. If you are in the league please contact an admin for help.")

    @commands.guild_only()
    @commands.command(aliases=["ca"])
    async def checkAvailability(self, ctx: Context, tier_name: str, match_day: str = None):
        if match_day is None:
            match_day = await self.match_cog._match_day(ctx)
        tier = await self.team_manager_cog._match_tier_name(ctx, tier_name)
        if tier is None:
            await ctx.send("No tier with name: `{0}`".format(tier_name))
            return

        tier_list = await self._tier_data(ctx.guild, match_day, tier)
        perm_fa_role = self.team_manager_cog._find_role_by_name(ctx, self.team_manager_cog.PERM_FA_ROLE)

        message = ""
        for member_id in tier_list:
            member: discord.Member = ctx.guild.get_member(member_id)
            if member is not None and await self.find_tier_from_fa_role(ctx, member) is not None:
                message += "\n{0}".format(member.display_name)
                if perm_fa_role is not None and perm_fa_role in member.roles:
                    message += " (Permanent FA)"

        color = discord.Colour.blue()
        for role in ctx.guild.roles:
            if role.name.lower() == tier_name.lower():
                color = role.color
        embed = discord.Embed(title="Availability for {0} tier on match day {1}:".format(tier, match_day), color=color, 
            description=message, thumbnail=ctx.guild.icon_url)
                    
        await ctx.send(embed=embed)

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearAvailability(self, ctx: Context, tier: str = None, match_day: str = None):
        if match_day is None:
            match_day = await self.match_cog._match_day(ctx)

        if tier is None:
            await self._save_match_data(ctx.guild, match_day, {})
        else:
            await self._save_tier_data(ctx.guild, match_day, tier, [])
        await ctx.send("Done.")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearAllAvailability(self, ctx: Context):
        await self._save_check_ins(ctx.guild, {})
        await ctx.send("Done.")

#endregion

#region helper methods

    async def send_check_in_message(self, ctx: Context, member: discord.Member, match_day, tier):
        embed = discord.Embed(title="Check In", 
            description="By checking in you are letting GMs know that you are available to play "
                "on the following match day in the following tier. To confirm react with {}".format(ReactionPredicate.YES_OR_NO_EMOJIS[0]),
            colour=discord.Colour.blue())
        embed.add_field(name="Match Day", value=match_day, inline=True)
        embed.add_field(name="Tier", value=tier, inline=True)

        react_msg = await member.send(embed=embed)
        start_adding_reactions(react_msg, ReactionPredicate.YES_OR_NO_EMOJIS)

        try:
            pred = ReactionPredicate.yes_or_no(react_msg, member)
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=VERIFY_TIMEOUT)
            if pred.result is True:
                await self.register_member(ctx.guild, member, match_day, tier)
                await member.send("Thank you for checking in! GMs will now be able to see that you're available.")
            else:
                await member.send("Not checked in. If you wish to check in use the command again.")
        except asyncio.TimeoutError:
            await member.send("Sorry, you didn't react quick enough. Please try again.")

    async def send_check_out_message(self, ctx: Context, member: discord.Member, match_day, tier):
        embed = discord.Embed(title="Check Out", 
            description="You are currently checked in as available for the following match day and tier. "
                "Do you wish to take yourself off the availability list? To confirm you want to check out, react with {}".format(ReactionPredicate.YES_OR_NO_EMOJIS[0]),
            colour=discord.Colour.blue())
        embed.add_field(name="Match Day", value=match_day, inline=True)
        embed.add_field(name="Tier", value=tier, inline=True)

        react_msg = await member.send(embed=embed)
        start_adding_reactions(react_msg, ReactionPredicate.YES_OR_NO_EMOJIS)

        try:
            pred = ReactionPredicate.yes_or_no(react_msg, member)
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=VERIFY_TIMEOUT)
            if pred.result is True:
                await self.unregister_member(ctx.guild, member, match_day, tier)
                await member.send("You have been removed from the list. Thank you for updating your availability!")
            else:
                await member.send("Still checked in. If you wish to check out use the command again.")
        except asyncio.TimeoutError:
            await member.send("Sorry, you didn't react quick enough. Please try again.")

    async def register_member(self, guild: discord.Guild, member: discord.Member, match_day, tier):
        tier_list = await self._tier_data(guild, match_day, tier)
        tier_list.append(member.id)
        await self._save_tier_data(guild, match_day, tier, tier_list)

    async def unregister_member(self, guild: discord.Guild, member: discord.Member, match_day, tier):
        tier_list = await self._tier_data(guild, match_day, tier)
        tier_list.remove(member.id)
        await self._save_tier_data(guild, match_day, tier, tier_list)

    async def find_tier_from_fa_role(self, ctx: Context, member: discord.Member):
        tiers = await self.team_manager_cog.tiers(ctx)
        for tier in tiers:
            fa_role = self.team_manager_cog._find_role_by_name(ctx, tier + "FA")
            if fa_role in member.roles:
                return tier
        return None

#endregion

#region load/save methods

    async def _tier_data(self, guild: discord.Guild, match_day, tier):
        match_data = await self._match_data(guild, match_day)
        tier_data = match_data.setdefault(tier, [])
        return tier_data

    async def _save_tier_data(self, guild: discord.Guild, match_day, tier, tier_data):
        check_ins = await self._check_ins(guild)
        match_data = check_ins.setdefault(match_day, {})
        match_data[tier] = tier_data
        await self._save_check_ins(guild, check_ins)

    async def _match_data(self, guild: discord.Guild, match_day):
        check_ins = await self._check_ins(guild)
        match_data = check_ins.setdefault(match_day, {})
        return match_data

    async def _save_match_data(self, guild: discord.Guild, match_day, match_data):
        check_ins = await self._check_ins(guild)
        check_ins[match_day] = match_data
        await self._save_check_ins(guild, check_ins) 

    async def _check_ins(self, guild: discord.Guild):
        return await self.config.guild(guild).CheckIns()

    async def _save_check_ins(self, guild: discord.Guild, check_ins):
        await self.config.guild(guild).CheckIns.set(check_ins)

#endregion
