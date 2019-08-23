import discord
import asyncio

from redbot.core import commands
from redbot.core import checks
from redbot.core.utils.predicates import MessagePredicate
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions

verify_timeout = 30

class Notice(commands.Cog):
    """Used to send a notice to a specified channel and ping the specified role(s)"""

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def notice(self, ctx, *pingRole: discord.Role):
        """Sends a notice to a channel and pings the specified role(s). The message and channel are given in a prompt
        
        Arguments:
            pingRole -- Can be 1 or more roles that you want to ping in the notice

        Notice will be in this format:
            @role(s)
            
            [message]"""

        try:
            await ctx.send("**What is the message you want to send?**\nIf you want to cancel this command just type `{}cancel`".format(ctx.prefix))
            pred = MessagePredicate.cancelled(ctx)
            await ctx.bot.wait_for("message", check=pred, timeout=verify_timeout)
            if pred.result is True:
                await ctx.send("Notice command canceled")
                return
            else:
                message = pred.result


            await ctx.send("**Which channel do you want to post the notice in?**\nYou have {} seconds to respond before this times out".format(verify_timeout))
            pred = MessagePredicate.valid_text_channel(ctx)
            await ctx.bot.wait_for("message", check=pred, timeout=verify_timeout)
            channel = pred.result

            formatted_message = "```@{0}\n\n{1}```".format(" @".join([role.name for role in pingRole]), message)
            notice_check = await ctx.send(formatted_message)
            react_msg = await ctx.send("**Are you ready to send this notice now?**")
            start_adding_reactions(react_msg, ReactionPredicate.YES_OR_NO_EMOJIS)

            pred = ReactionPredicate.yes_or_no(react_msg, ctx.author)
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=verify_timeout)
            if pred.result is True:
                #make all the roles in pingRoles mentionable and save their original state
                mentionable = []
                for role in pingRole:
                    mentionable.append(role.mentionable)
                    if not role.mentionable:
                        await role.edit(mentionable=True)

                final_notice = "{0}\n\n{1}".format(" ".join([role.mention for role in pingRole]), message)
                await channel.send(final_notice)
                await ctx.channel.delete_messages([notice_check, react_msg])

                #reset roles back to their original state
                index = 0
                for role in pingRole:
                    await role.edit(mentionable=mentionable[index])
                    index += 1

                await ctx.send("Done")
            else:
                await ctx.send("Notice not sent")
        except asyncio.TimeoutError:
            await ctx.send("Response timed out. Notice not sent.")