import re
import discord
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks

defaults = {"Applications": []}

# TODO: (All listed todos) +league approve applications, alert all game players when match has been updated, include which stream its on

class StreamSignupManager(commands.Cog):
    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567892, force_registration=True)
        self.config.register_guild(**defaults)
        self.match_cog = bot.get_cog("Match")
        self.team_manager_cog = bot.get_cog("TeamManager")
        self.bot = bot
    
    @commands.command(aliases=["applications", "getapps", "listapps"])
    @commands.guild_only()
    async def viewapps(self, ctx):
        applications = await self._applications(ctx.guild)
        message = "Pending applications ({}):".format(len(applications))
        if applications:
            for app in applications:
                message += "\nMD {0}: {1} vs. {2} at {3} (Status: {4})".format(
                    app['match_day'],
                    app['requested_by'],
                    app['request_recipient'],
                    app['stream_slot'],
                    app['status']
                )
            await ctx.send(message)
            return True
        await ctx.send("\n{0}\n\t(None)".format(message))
        return False


    @commands.command(aliases=["streamapply", "afs"])
    @commands.guild_only()
    async def applyForStream(self, ctx, match_day, stream_slot):
        requesting_member = ctx.message.author
        requesting_team = await team_manager_cog.get_current_team_name(ctx, requesting_member)
        match = await self.match_cog.get_match_from_day_team(ctx, match_day, other_team)

        if match['home'] == requesting_team:
            other_team = match['away']
        elif match['away'] == requesting_team:
            other_team = match['away']
        else:
            await ctx.send(":x: Opposing team not found.")
            return False

        other_franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, other_team)
        other_captain = await self.team_manager_cog.get_team_captain(ctx, other_franchise_role, tier_role)
        
        # send request to GM if team has no captain
        if not other_captain:
            other_captain = self.team_manager_cog._get_gm(ctx, other_franchise_role)

        await self._add_application(ctx.guild, requesting_member, match stream_slot)

        message = ("You have been asked to play **match day {0}** ({} vs. {}) on stream at the **{1} time slot**. "
        "Please respond to this request in the **#{2}** channel in the **{3}** server with one of the following:"
        "\n\t - To accept: `[p]streamapp accept {0}`"
        "\n\t - To reject: `[p]streamapp reject {0}`"
        "\nThis stream application will not be considered until you respond.").format(match_day, stream_slot, ctx.channel, ctx.guild)
        await self._send_member_message(ctx, other_captain, message)

    @commands.command(aliases=["streamapp", "streamApplications", "streamapplications"])
    @commands.guild_only()
    async def streamApp(self, ctx, action, match_day):
        # possible improvement: maybe make this central command
        if action not in ["accept", "reject"]:
            await ctx.send("\"{0}\" is not a recognized action. Please either _accept_ or _reject_ the stream application.".format(response))
            return False

        accepted = True if action == "accept" else False
        updated = await self._update_application(ctx.guild, ctx.author, match_day, accepted)
        if updated:
            if accepted:
                await ctx.send("Your application to play match {0} on stream has been updated.".format(match_day))
                return True
            else:
                await ctx.send("Your application to play match {0} on stream has been removed.".format(match_day))
                return True
        else:
            await ctx.send(":x: Stream Application not found.")

    @commands.command(aliases=['clearapps', 'removeapps'])
    @commands.guild_only()
    async def clearApps(self, ctx):
        await self._clear_applications(ctx.guild)
        await ctx.send("Done.")

    async def _add_application(self, guild, requested_by, match_data, stream_slot, time_slot=None):
        #TODO: avoid duplicate applications
        applications = await self._applications(guild)
        # Match format:
        # match_data = {
        #     'matchDay': match_day,
        #     'matchDate': match_date,
        #     'home': home,
        #     'away': away,
        #     'roomName': roomName,
        #     'roomPass': roomPass
        # }
        new_payload = {
            "status": "PENDING_OPP_CONFIRMATION", # pending opponent confirmation
            "requested_by": requested_by.id,
            "request_recipient": request_recipient.id,
            "home_team": match_data['home'],
            "away_team": match_data['away'],
            "match_day": match_day,
            "stream_slot": stream_slot
            "time_slot": time_slot
        }
        #Possible improvement: Update match info instead of adding a new field/don't duplicate saved data/get match ID reference?
        applications.append(new_payload)
        await self._save_applications(guild, applications)

    async def _update_application(self, guild, recipient, match_day, is_accepted):
        applications = self._applications(guild)
        for app in applications:
            if app['request_recipient'] == recipient.id and app['match_day'] == match_day:
                if app['status'] == "PENDING_OPP_CONFIRMATION":
                    if is_accepted:
                        app['status'] == "PENDING_LEAGUE_APPROVAL"
                        await self._save_applications(guild, applications)
                        # TODO: send update to requesting player, send alert to media channel feed
                        return True
                    else:
                        applications.remove(app)
                        await self._save_applications(guild, applications)
                        # TODO: send rejection message to requesting player
                        return True
        return False

    async def _applications(self, guild):
        return await self.config.guild(guild).Applications()

    async def _save_applications(self, guild, applications):
        await self.config.guild(guild).Applications.set(applications)

    async def _clear_applications(self, guild):
        await self.config.guild(guild).Applications.set([])
    
    async def _send_member_message(self, ctx, member, message):
        message_title = "**Message from {0}:**\n\n".format(ctx.guild.name)
        message = message.replace('[p]', ctx.prefix)
        message = message_title + message
        return await member.send(message)

    def _get_member_from_id(self, guild, member_id):
        for member in guild.members:
            if member.id == member_id:
                return member
        return None
