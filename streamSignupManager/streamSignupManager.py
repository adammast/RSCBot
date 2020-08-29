import re
import discord
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks

defaults = {"Applications": {}, "Schedule": {}, "Time_Slots": {1: "11:00pm ET", 2: "11:30pm ET"}, "Stream_Channel": None}

# TODO: (All listed todos) +league approve applications, alert all game players when match has been updated, include which stream its on

class StreamSignupManager(commands.Cog):
    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567892, force_registration=True)
        self.config.register_guild(**defaults)
        self.match_cog = bot.get_cog("Match")
        self.team_manager_cog = bot.get_cog("TeamManager")
        self.bot = bot
    
    @commands.command(aliases=["applications", "getapps", "listapps", "apps"])
    @commands.guild_only()
    async def viewapps(self, ctx, match_day=None, stream_slot=None):
        applications = await self._applications(ctx.guild)
        message = "Pending applications ({}):".format(len(applications))
        if applications:
            for app in applications:
                if match_day == app['match_day'] or not match_day:
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
        
    @commands.command(aliases=["streamapp", "streamapply", "streamApplications", "streamapplications"])
    @commands.guild_only()
    async def streamApp(self, ctx, action, match_day, stream_slot=None):
        if action == "apply":
            if not stream_slot:
                await ctx.send(":x: stream slot must be included in an application.")
                return False
            requesting_member = ctx.message.author
            requesting_team = await team_manager_cog.get_current_team_name(ctx, requesting_member)
            match = await self.match_cog.get_match_from_day_team(ctx, match_day, other_team)
            
            applied = await self._add_application(ctx.guild, requesting_member, match, stream_slot)
            if applied:
                await ctx.send("Done.")
                return True
        if action not in ["accept", "reject"]:
            await ctx.send("\"{0}\" is not a recognized action. Please either _accept_ or _reject_ the stream application.".format(response))
            return False

        accepted = True if action == "accept" else False
        updated = await self._accept_reject_application(ctx.guild, ctx.author, match_day, accepted)
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

    @commands.command(aliases=['reviewapps', 'reviewApplications', 'approveApps'])
    @commands.guild_only()
    async def reviewApps(self, ctx, match_day=None):
        applications = await self._applications(ctx.guild)
        message = "Pending applications ({}):".format(len(applications))
        if applications:
            for app in applications:
                if match_day == app['match_day'] or not match_day:
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


    async def _add_application(self, ctx, requested_by, match_data, stream_slot):
        applications = await self._applications(ctx.guild)
        if self._get_application(match_data):
            await ctx.send(":x: Application is already in progress.")
            return False
            
        requesting_team = await team_manager_cog.get_current_team_name(ctx, requesting_member)
        if match_data['home'] == requesting_team:
            other_team = match_data['away']
        else:
            other_team = match_data['home']
        other_franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, other_team)
        other_captain = await self.team_manager_cog.get_team_captain(ctx, other_franchise_role, tier_role)
        # send request to GM if team has no captain
        if not other_captain:
            other_captain = self.team_manager_cog._get_gm(ctx, other_franchise_role)

        new_payload = {
            "status": "PENDING_OPP_CONFIRMATION", # pending opponent confirmation
            "requested_by": requested_by.id,
            "request_recipient": other_captain.id,
            "home_team": match_data['home'],
            "away_team": match_data['away'],
            "stream_slot": stream_slot,
            "time_slot": None
        }
        
        # Possible improvement: Update match info instead of adding a new field/don't duplicate saved data/get match ID reference?
        # Add application
        application[match_day].append(new_payload)
        await self._save_applications(ctx.guild, applications)

        # Challenge other team
        message = challenged_message.format(match_day=match_day, home=home, away=away, stream_slot=stream_slot, channel=ctx.channel)
        await self._send_member_message(ctx, other_captain, message)

        return True

    async def _accept_reject_application(self, guild, recipient, match_day, is_accepted):
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

    async def _stream_schedule(self, guild):
        return await self.config.guild(guild).Schedule()

    async def _get_application(self, guild, match):
        for app in await self._applications(guild):
            if app['home_team'] == match['home'] and app['match_day'] == match['matchDay']:
                return app
        return None

    async def _save_applications(self, guild, applications):
        await self.config.guild(guild).Applications.set(applications)

    async def _save_stream_schedule(self, guild, schedule):
        await self.config.guild(guild).Schedule.set(schedule)

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

challenged_msg = ("You have been asked to play **match day {match_day}** ({home} vs. {away}) on stream at the **{time_slot} time slot**. "
    "Please respond to this request in the **#{channel}** channel with one of the following:"
    "\n\t - To accept: `[p]streamapp accept {match_day}`"
    "\n\t - To reject: `[p]streamapp reject {match_day}`"
    "\nThis stream application will not be considered until you respond.")

challenge_accepted_msg = (":white_check_mark: Your stream application for **match day {match_day}** ({home} vs. {away}) has been accepted by your opponents, and is "
    "now pending league approval. An additional message will be sent when a decision is made regarding this application.")

challenge_rejected_msg = (":x: Your stream application for **match day {match_day}** ({home} vs. {away}) has been rejected by your opponents, and will "
    "not be considered moving forward.")

#TODO: add stream channel (rsc vs rsc_2, etc)
league_approved_msg = ("**Congratulations!** You have been selected to play **match day {match_day}** ({home} vs. {away}) on stream at "
    "the **{3} time slot**. Feel free to use the `[p]match {match_day}` in your designated bot input channel see updated "
    "details of this match. We look forward to seeing you on stream!")

league_rejected_msg = ("Your application to play **match day {match_day}** ({home} vs. {away}) on stream has been denied. "
    "However, we will keep your application on file in case anything changes.")

