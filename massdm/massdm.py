from typing import List

import discord
from discord.ext import commands

from .utils import checks


class MassDM:

    """Send a direct message to all members of the specified Role."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_users_with_role(self, guild: discord.Guild,
                             role: discord.Role) -> List[discord.User]:
        roled = []
        for member in guild.members:
            if role in member.roles:
                roled.append(member)
        return roled

    @commands.command(no_pm=True, name="massdm2", aliases=["mdm2"])
    @checks.mod_or_permissions(administrator=True)
    async def _mdm(self, ctx, role: discord.Role, *, message: str):
        """Sends a DM to all Members with the given Role.
        Allows for the following customizations:
        {0} is the member being messaged.
        {1} is the role they are being message through.
        {2} is the person sending the message.
        """

        guild = ctx.message.guild
        sender = ctx.message.author

        dm_these = self._get_users_with_role(guild, role)

        for user in dm_these:
            try:
                await user.send(message.format(user, role, sender))
            except (discord.Forbidden, discord.HTTPException):
                continue

        await ctx.send("Done")


def setup(bot: commands.Bot):
    bot.add_cog(MassDM(bot))