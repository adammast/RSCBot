import discord
import asyncio
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions

defaults = {"Applications": {}, "Schedule": {}, "TimeSlots": {}, "LiveStreamChannels": [], "StreamFeedChannel": None}
verify_timeout = 30

# TODO: 
# - make [p]clearStreamSchedule notify players of stream removal
# + (maybe?) reject applications for same time frame/alert that a different application has been accepted.

# Roles: Captain, GM, <Tier>, <Franchise>, Media Committee

class StreamSignupManager(commands.Cog):
    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567892, force_registration=True)
        self.config.register_guild(**defaults)
        self.match_cog = bot.get_cog("Match")
        self.team_manager_cog = bot.get_cog("TeamManager")
        self.bot = bot
        self.MEDIA_ROLE_STR = "Media Committee"

        # Application statuses
        self.PENDING_OPP_CONFIRMATION_STATUS = "PENDING_OPP_CONFIRMATION"
        self.PENDING_LEAGUE_APPROVAL_STATUS = "PENDING_LEAGUE_APPROVAL"
        self.SCHEDULED_ON_STREAM_STATUS = "SCHEDULED_ON_STREAM"
        self.REJECTED_STATUS = "REJECTED"
        self.RESCINDED_STATUS = "RESCINDED"
    
    @commands.group(aliases=["streamapp", "streamapply", "streamApplications", "streamapplications"])
    @commands.guild_only()
    async def streamApp(self, ctx):
        """
        Central command for managing stream signups. This is used to initiate stream applications, as well as accepting/rejecting requests to play on stream.

        The team parameter is ignored if you are not a General Manager.
        
        **Examples:**
        [p]streamApp apply 1 1
        [p]streamApp accept 3
        [p]stream reject 3

        Note: If you are a **General Manager**, you must include the team name in applications
        [p]streamApp apply 1 1 Spartans
        [p]streamApp accept 4 Vikings
        [p]streamApp reject 3 Vikings
        """

    @commands.guild_only()
    @streamApp.command(aliases=['challenge'])
    async def apply(self, ctx, match_day, time_slot=None, team=None):
        """Initiate a stream application for a given match day"""
        requesting_member = ctx.message.author
        gm_role = self.team_manager_cog._find_role_by_name(ctx, self.team_manager_cog.GM_ROLE)
        if gm_role in requesting_member.roles:
            if not team:
                await ctx.send(":x: GMs must include their team name in streamApp commands.")
                return False
            if not await self._verify_gm_team(ctx, requesting_member, team):  # function contains error message
                return False
        else:
            team = await team_manager_cog.get_current_team_name(ctx, requesting_member)

        if not time_slot:
            await ctx.send(":x: stream slot must be included in an application.")
            return False
            
        match = await self.match_cog.get_match_from_day_team(ctx, match_day, team)
        if not match:
            await ctx.send("No match found for {team} on match day {match_day}".format(team=team, match_day=match_day))
        
        if not await self._get_time_from_slot(ctx.guild, time_slot):
            await ctx.send(":x: {0} is not a valid time slot".format(time_slot))
            return False
        
        applied = await self._add_application(ctx, requesting_member, match, time_slot, team)
        if applied:
            await ctx.send("Done.")
            return True
        return False
    
    @commands.guild_only()
    @streamApp.command()
    async def accept(self, ctx, match_day, team=None):
        """Accept a challenge to play on stream, and complete the joint application for the proposed stream slot"""
        requesting_member = ctx.message.author
        gm_role = self.team_manager_cog._find_role_by_name(ctx, self.team_manager_cog.GM_ROLE)
        if gm_role in requesting_member.roles:
            if not team:
                await ctx.send(":x: GMs must include their team name in streamApp commands.")
                return False
            if not await self._verify_gm_team(ctx, requesting_member, team):  # function contains error message
                return False
            updated = await self._accept_reject_application(ctx, ctx.author, match_day, True, team)
        else:
            updated = await self._accept_reject_application(ctx, ctx.author, match_day, True)
        
        if updated:
            await ctx.send("Your application to play match day {0} on stream has been updated.".format(match_day))
            return True
        else:
            await ctx.send(":x: Stream Application not found.")
    
    @commands.guild_only()
    @streamApp.command()
    async def reject(self, ctx, match_day, team=None):
        """Reject a challenge to play on stream."""
        requesting_member = ctx.message.author
        gm_role = self.team_manager_cog._find_role_by_name(ctx, self.team_manager_cog.GM_ROLE)
        if gm_role in requesting_member.roles:
            if not team:
                await ctx.send(":x: GMs must include their team name in streamApp commands.")
                return False
            if not await self._verify_gm_team(ctx, requesting_member, team):  # function contains error message
                return False
            updated = await self._accept_reject_application(ctx, ctx.author, match_day, False, team)
        else:
            updated = await self._accept_reject_application(ctx, ctx.author, match_day, False)
    
        if updated:
            await ctx.send("You have denied your application to play match day {0} on stream.".format(match_day))
            return True
        else:
            await ctx.send(":x: Stream Application not found.")


    @commands.command(aliases=['apps', 'reviewapps', 'reviewApplications'])
    @commands.guild_only()
    async def reviewApps(self, ctx, match_day=None, time_slot=None):
        """
        View all completed stream applications that are pending league approval. Match Day and Time Slot filters are optional.
        """
        media_role = self.team_manager_cog._find_role_by_name(ctx, self.MEDIA_ROLE_STR)
        if not media_role or media_role not in ctx.message.author.roles:
            await ctx.send(":x: You must have the **{0}** role to run this command.".format(self.MEDIA_ROLE_STR))
            return False
        
        message = await self._format_apps(ctx, True, match_day, time_slot)
        if message:
            await ctx.send(message)
        else:
            message = "No completed applications have been found"
            if match_day:
                message += " for match day {0}".format(match_day)
            if time_slot:
                message += " (time slot {0})".format(time_slot)
            message += "."
            await ctx.send(message)

    @commands.command(aliases=['allapps', 'wipapps'])
    @commands.guild_only()
    async def allApps(self, ctx, match_day=None, time_slot=None):
        """
        View all stream applications and their corresponding statuses. This is largely used for debugging purposes.
        """
        media_role = self.team_manager_cog._find_role_by_name(ctx, self.MEDIA_ROLE_STR)
        if not media_role or media_role not in ctx.message.author.roles:
            await ctx.send(":x: You must have the **{0}** role to run this command.".format(self.MEDIA_ROLE_STR))
            return False
        
        message = await self._format_apps(ctx, False, match_day, time_slot)
        if message:
            await ctx.send(message)
        else:
            message = "No pending applications have been found"
            if match_day:
                message += " for match day {0}".format(match_day)
            if time_slot:
                message += " (time slot {0})".format(time_slot)
            message += "."
            await ctx.send(message)

    @commands.command(aliases=['clearapps', 'removeapps'])
    @commands.guild_only()
    async def clearApps(self, ctx):
        """Clears all saved applications."""
        media_role = self.team_manager_cog._find_role_by_name(ctx, self.MEDIA_ROLE_STR)
        if not media_role or media_role not in ctx.message.author.roles:
            await ctx.send(":x: You must have the **{0}** role to run this command.".format(self.MEDIA_ROLE_STR))
            return False
        
        await self._clear_applications(ctx.guild)
        await ctx.send("Done.")

    @commands.guild_only()
    @commands.command(aliases=['acceptapp'])
    @commands.guild_only()
    async def approveApp(self, ctx, url_or_id, match_day, team):
        """Approve application for stream.
        
        Applications that have `PENDING_LEAUGE_APPROVAL`, `REJECTED`, or `RESCINDED` status may be approved."""
        media_role = self.team_manager_cog._find_role_by_name(ctx, self.MEDIA_ROLE_STR)
        if not media_role or media_role not in ctx.message.author.roles:
            await ctx.send(":x: You must have the **{0}** role to run this command.".format(self.MEDIA_ROLE_STR))
            return False
        
        apps = await self._applications(ctx.guild)
        stream_channel = await self._get_live_stream(ctx.guild, url_or_id)
        if not stream_channel:
            await ctx.send("\"__{url}__\" is not a valid url or id association. Use `{p}getLiveStreams` to see registered live stream pages.".format(url=url_or_id, p=ctx.prefix))
            return False
        for app in apps[match_day]:
            if (app['status'] == (self.PENDING_LEAGUE_APPROVAL_STATUS or app['status'] == self.REJECTED_STATUS or app['status'] == self.RESCINDED_STATUS)
                and (app['home'] == team or app['away'] == team)):
                # Update App Status
                app['status'] = self.SCHEDULED_ON_STREAM_STATUS
                slot = app['slot']

                # Add to Stream Schedule
                scheduled = await self._schedule_match_on_stream(ctx, stream_channel, match_day, app['slot'], app['home'], app['away'])
                
                if scheduled:
                    await self._save_applications(ctx.guild, apps)
                
                await ctx.send("Done.")
                return True

        await ctx.send("Stream Application could not be found.")

    @commands.guild_only()  
    @commands.command(aliases=['rejectapp'])
    @commands.guild_only()
    async def rejectApp(self, ctx, match_day, team):
        """Reject application for stream"""
        media_role = self.team_manager_cog._find_role_by_name(ctx, self.MEDIA_ROLE_STR)
        if not media_role or media_role not in ctx.message.author.roles:
            await ctx.send(":x: You must have the **{0}** role to run this command.".format(self.MEDIA_ROLE_STR))
            return False
        
        apps = await self._applications(ctx.guild)
        # stream_channel = self._get_live_stream(ctx.guild, url_or_id)
        for app in apps[match_day]:
            if (app['home'] == team or app['away'] == team) and app['status'] == self.PENDING_LEAGUE_APPROVAL_STATUS:
                # Update App Status
                app['status'] = self.REJECTED_STATUS
                await self._save_applications(ctx.guild, apps)

                # Inform applicants that their application has been rejected
                message = league_rejected_msg.format(match_day=match_day, home=app['home'], away=app['away'])
                for member_id in [app['requested_by'], app['request_recipient']]:
                    member = self._get_member_from_id(ctx.guild, member_id)
                    await self._send_member_message(ctx, member, message)
            
                await ctx.send("Done.")
                return True
        await ctx.send(":x: Stream Application could not be found.")
    
    @commands.guild_only()
    @commands.command(aliases=['setmatchonstream'])
    @commands.guild_only()
    async def setMatchOnStream(self, ctx, stream_url_or_id, match_day, slot, team):
        """
        Override application process and set match on stream
        
        **Examples:**
        [p]setMatchOnStream 1 1 1 Spartans
        [p]setMatchOnStream https://twitch.tv/rocketsoccarconfederation 2 8 Vikings
        """
        media_role = self.team_manager_cog._find_role_by_name(ctx, self.MEDIA_ROLE_STR)
        if not media_role or media_role not in ctx.message.author.roles:
            await ctx.send(":x: You must have the **{0}** role to run this command.".format(self.MEDIA_ROLE_STR))
            return False
        
        match = await self.match_cog.get_match_from_day_team(ctx, match_day, team)
        if not match:
            await ctx.send(":x: Match not found for {0} on match day {1}".format(team, match_day))
            return False
        
        stream_channel = await self._get_live_stream(ctx.guild, stream_url_or_id)
        if not stream_channel:
            await ctx.send(":x: \"{0}\" is not a valid stream url or id".format(url_or_id))
            return False
        
        time = await self._get_time_from_slot(ctx.guild, slot)
        if not time:
            await ctx.send(":x: \"{0}\" is not a valid time slot".format(slot))
            return False

        prompt = ("Bypass application process and schedule **{home}** vs. **{away}** (match day {match_day}) on stream?"
            "\nlive stream: <{live_stream}>\nstream slot: {stream_slot} - {time}").format(
                home=match['home'],
                away=match['away'],
                match_day=match_day,
                live_stream=stream_channel,
                stream_slot=slot,
                time=time
            )
        react_msg = await ctx.send(prompt)
        start_adding_reactions(react_msg, ReactionPredicate.YES_OR_NO_EMOJIS)
        try:
            pred = ReactionPredicate.yes_or_no(react_msg, ctx.message.author)
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=verify_timeout)
            if pred.result:
                scheduled = await self._schedule_match_on_stream(ctx, stream_channel, match_day, slot, match['home'], match['away'])
                if scheduled:
                    # Update app if one was ongoing
                    apps = await self._applications(ctx.guild)
                    try:
                        for app in apps[match_day]:
                            if (app['home'].casefold() == team.casefold() or app['away'].casefold() == team.casefold()):
                                app['status'] = self.SCHEDULED_ON_STREAM_STATUS
                                app['slot'] = slot
                                await self._save_applications(ctx.guild, apps)
                                break
                    except KeyError:
                        pass
                    
                    await ctx.send("Done.")
            else:
                await ctx.send("Match was not added to the stream schedule.")
        except asyncio.TimeoutError:
            await ctx.send("{0} You didn't react quick enough. Please try again.".format(ctx.author.mention))

    @commands.command(aliases=['schedule'])
    @commands.guild_only()
    async def streamSchedule(self, ctx, url_or_id=None, match_day=None):
        """View Matches that have been scheduled on stream
        
        `[p]streamSchedule today` may be used to see the schedule for the current week's stream matches.
        """
        schedule = await self._stream_schedule(ctx.guild)
        url = None
        this_week_only = False
        title = "Stream Schedule"
        if url_or_id:
            if url_or_id.casefold() in ["today", "tonight", "this-week"]:
                this_week_only = True
                match_day = await self.match_cog._match_day(ctx)
            else:
                url = await self._get_live_stream(ctx.guild, url_or_id)
                if not url:
                    await ctx.send(":x: \"{0}\" is not a valid live stream indicator.".format(url_or_id))
                    return False
                if match_day:
                    title += " (match day {0})".format(match_day)
        title += ":"
        message = title
        # Print Schedule as Quote
        current_match_day = await self.match_cog._match_day(ctx)
        num_matches = 0
        for this_url, match_days in schedule.items():
            if url == this_url or not url:
                # For Each Stream Page
                stream_header = "\n> __**<{0}> Schedule**__".format(this_url) if "https://" in this_url else "\n> __**{0} Schedule**__".format(this_url)
                tmp_message = ""
                # message += stream_header
                for this_match_day, time_slots in sorted(match_days.items()):
                    # logic for whether or not to add matches for that match day
                    add_matches = (
                        (this_week_only and match_day == this_match_day) or 
                        (not this_week_only and (match_day == this_match_day or (not match_day and this_match_day >= current_match_day)))
                    )
                    if add_matches:
                        tmp_message += "\n> \n> __**Match Day {0}**__".format(this_match_day)
                        for time_slot, match in sorted(time_slots.items()):
                            tmp_message += "\n> {0} | {1} vs. {2}".format(time_slot, match['home'], match['away'])
                            num_matches += 1

                # Don't add stream to schedule preview unless it has matches that will be displayed in result
                if tmp_message:
                    if num_matches and message != title:
                        message += "\n> \n> "
                    message += stream_header
                    message += tmp_message

        if not num_matches:
            message = ":x: No stream matches have been scheduled"
            if not url and match_day:
                message = ":x: \"{0}\" is not a valid url or live stream id"
            else:
                if match_day:
                    message += " for match day {0}".format(match_day)
                if url:
                    message += " on <{0}>".format(url) if "https://" in url else " on <{0}>".format(url)
            message += "."

        await ctx.send(message)

    @commands.command(aliases=['getstreamlobbiess', 'streamLobbyInfo', 'streamlobbies'])
    @commands.guild_only()
    async def getStreamLobbies(self, ctx, stream_url_or_id=None, match_day=None):
        """Get Private Lobby information for matches that will be scheduled on stream"""
        media_role = self.team_manager_cog._find_role_by_name(ctx, self.MEDIA_ROLE_STR)
        if not media_role or media_role not in ctx.message.author.roles:
            await ctx.send(":x: You must have the **{0}** role to run this command.".format(self.MEDIA_ROLE_STR))
            return False
    
        # Parse match day to int
        if match_day:
            try:
                match_day = int(match_day)
                match_day = str(match_day)
            except:
                await ctx.send("\"{}\" is not a valid match day. Defaulting to current match day.".format(match_day))
                match_day = None
            pass

        # Set match_day to today if not specified
        if not match_day:
            match_day = await self.match_cog._match_day(ctx)

        lobbies_embeds = []
        if stream_url_or_id:
            live_stream = await self._get_live_stream(ctx.guild, stream_url_or_id)
            if not live_stream:
                await ctx.send(":x: {0} is not a valid stream url or ID".format(stream_url_or_id))
                return False
            
            embed = await self._format_match_lobby_info(ctx, match_day, live_stream)
            if embed:
                lobbies_embeds.append(embed)
        else:
            for live_stream in await self._get_live_stream_channels(ctx.guild):
                embed = await self._format_match_lobby_info(ctx, match_day, live_stream)
                if embed:
                    lobbies_embeds.append(embed)

        # Delete original message
        if not lobbies_embeds:
            await ctx.send(":x: No stream matches found.")
            return False
        
        # Send lobby info in DMs
        if lobbies_embeds:
            await ctx.message.delete()
            for lobbies_embed in lobbies_embeds:
                await ctx.message.author.send(embed=lobbies_embed)

    @commands.guild_only()
    @commands.command(aliases=['clearschedule'])
    async def clearStreamSchedule(self, ctx):
        """Removes stream schedule
        Note: This will **not** update information in the match cog."""

        media_role = self.team_manager_cog._find_role_by_name(ctx, self.MEDIA_ROLE_STR)
        if not media_role or media_role not in ctx.message.author.roles:
            await ctx.send(":x: You must have the **{0}** role to run this command.".format(self.MEDIA_ROLE_STR))
            return False
        
        msg = "Are you sure you want to remove all scheduled live stream matches?"
        react_msg = await ctx.send(msg)
        start_adding_reactions(react_msg, ReactionPredicate.YES_OR_NO_EMOJIS)
        try:
            pred = ReactionPredicate.yes_or_no(react_msg, ctx.message.author)
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=verify_timeout)
            if pred.result:
                await self._save_stream_schedule(ctx.guild, {})
                await ctx.send("Done.")
            else:
                await ctx.send("Live Stream Schedule was not modified or removed.")
        except asyncio.TimeoutError:
            await ctx.send("{0} You didn't react quick enough. Please try again.".format(ctx.author.mention))

    @commands.guild_only()
    @commands.command(aliases=['rescindStreamGame'])
    @checks.admin_or_permissions(manage_guild=True)
    async def rescindStreamMatch(self, ctx, match_day, team):
        """Removes a match from the stream schedule"""
        media_role = self.team_manager_cog._find_role_by_name(ctx, self.MEDIA_ROLE_STR)
        if not media_role or media_role not in ctx.message.author.roles:
            await ctx.send(":x: You must have the **{0}** role to run this command.".format(self.MEDIA_ROLE_STR))
            return False
        
        schedule = await self._stream_schedule(ctx.guild)
        if schedule:
            match_found = await self._get_stream_match(ctx, match_day, team)
            if match_found:
                match, slot = match_found
                msg = ("__Match found.__\n**{home}** vs. **{away}**"
                    "\nMatch Day {match_day}, time slot {slot}\n\nRemove this match from the "
                    "stream schedule?").format(home=match['home'], away=match['away'], match_day=match_day, slot=slot)
                react_msg = await ctx.send(msg)
                start_adding_reactions(react_msg, ReactionPredicate.YES_OR_NO_EMOJIS)
                try:
                    pred = ReactionPredicate.yes_or_no(react_msg, ctx.message.author)
                    await ctx.bot.wait_for("reaction_add", check=pred, timeout=verify_timeout)
                    if pred.result:
                        if await self._remove_match_from_stream(ctx, match_day, team, notify_teams=True):
                            await ctx.send("Done.")
                        else:
                            await ctx.send(":x: Match was not found in the stream schedule.")
                    else:
                        await ctx.send("No changes made.")
                except asyncio.TimeoutError:
                    await ctx.send("{0} You didn't react quick enough. Please try again.".format(ctx.author.mention))
            else:
                await ctx.send(":x: Match was not found in the stream schedule.")
        else:
            await ctx.send("No games have been scheduled on stream.")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setStreamFeedChannel(self, ctx, channel: discord.TextChannel):
        """Sets the channel where all stream application notification messages will be posted"""
        media_role = self.team_manager_cog._find_role_by_name(ctx, self.MEDIA_ROLE_STR)
        if not media_role or media_role not in ctx.message.author.roles:
            await ctx.send(":x: You must have the **{0}** role to run this command.".format(self.MEDIA_ROLE_STR))
            return False

        await self._save_stream_feed_channel(ctx, channel.id)
        await ctx.send("Done.")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def getStreamFeedChannel(self, ctx):
        """Gets the channel currently assigned as the stream feed channel. Stream application updates are sent to this channel when it is set."""
        try:
            await ctx.send("Stream log channel set to: {0}".format((await self._stream_feed_channel(ctx)).mention))
        except:
            await ctx.send(":x: Stream log channel not set.")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def unsetStreamFeedChannel(self, ctx):
        """Unsets the stream feed channel."""
        await self._save_trans_channel(ctx, None)
        await ctx.send("Done.")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def addTimeSlot(self, ctx, slot, *, time):
        """Adds a time slot association"""
        media_role = self.team_manager_cog._find_role_by_name(ctx, self.MEDIA_ROLE_STR)
        if not media_role or media_role not in ctx.message.author.roles:
            await ctx.send(":x: You must have the **{0}** role to run this command.".format(self.MEDIA_ROLE_STR))
            return False
        
        if await self._get_time_from_slot(ctx.guild, slot):
            await ctx.send(":x: Time slot {0} is already registered.".format(slot))
            return False
        await self._add_time_slot(ctx.guild, slot, time)
        await ctx.send("Done.")

    @commands.guild_only()
    @commands.command(aliases=['timeSlots', 'timeslots', 'streamslots', 'viewTimeSlots'])
    async def getTimeSlots(self, ctx):
        """Lists all registered live stream time slots"""
        time_slots = await self._get_time_slots(ctx.guild)
        if time_slots:
            message = "__Stream Time Slots:__"
            for slot, time in time_slots.items():
                message += "\n{0} - {1}".format(slot, time)
        else:
            message = "No Stream Slots have been set."

        await ctx.send(message)

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def removeTimeSlot(self, ctx, slot):
        """Remove time slot association"""
        media_role = self.team_manager_cog._find_role_by_name(ctx, self.MEDIA_ROLE_STR)
        if not media_role or media_role not in ctx.message.author.roles:
            await ctx.send(":x: You must have the **{0}** role to run this command.".format(self.MEDIA_ROLE_STR))
            return False
        
        time_slots = await self.config.guild(ctx.guild).TimeSlots()

        try:
            del time_slots[slot]
            await self._save_time_slots(ctx.guild, time_slots)
            await ctx.send(time_slots)
            await ctx.send("Done.")
        except KeyError:
            await ctx.send(":x: {0} is not a registered time slot.".format(slot))

    @commands.guild_only()
    @commands.command(aliases=['cleartimeslots'])
    @checks.admin_or_permissions(manage_guild=True)
    async def clearTimeSlots(self, ctx):
        """Removes all time slot associations"""
        media_role = self.team_manager_cog._find_role_by_name(ctx, self.MEDIA_ROLE_STR)
        if not media_role or media_role not in ctx.message.author.roles:
            await ctx.send(":x: You must have the **{0}** role to run this command.".format(self.MEDIA_ROLE_STR))
            return False
        
        await self._save_time_slots(ctx.guild, {})
        await ctx.send("Done.")

    @commands.guild_only()
    @commands.command(aliases=['addStream'])
    @checks.admin_or_permissions(manage_guild=True)
    async def addLiveStream(self, ctx, url):
        """Adds a new live stream page for stream signups"""
        media_role = self.team_manager_cog._find_role_by_name(ctx, self.MEDIA_ROLE_STR)
        if not media_role or media_role not in ctx.message.author.roles:
            await ctx.send(":x: You must have the **{0}** role to run this command.".format(self.MEDIA_ROLE_STR))
            return False
        
        msg = "Add \"__{0}__\" to list of stream pages?".format(url)
        react_msg = await ctx.send(msg)
        start_adding_reactions(react_msg, ReactionPredicate.YES_OR_NO_EMOJIS)
        try:
            pred = ReactionPredicate.yes_or_no(react_msg, ctx.message.author)
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=verify_timeout)
            if pred.result:
                await self._add_live_stream_channel(ctx.guild, url)
                await ctx.send("Done.")
            else:
                await ctx.send("\"__{0}__\" was not added as a live stream page.".format(url))
        except asyncio.TimeoutError:
            await ctx.send("{0} You didn't react quick enough. Please try again.".format(ctx.author.mention))
    
    @commands.guild_only()
    @commands.command(aliases=['livestreams', 'liveStreams'])
    @checks.admin_or_permissions(manage_guild=True)
    async def getLiveStreams(self, ctx):
        """Lists all saved live stream channels"""
        channels = await self._get_live_stream_channels(ctx.guild)
        if channels:
           message = "__Live Stream Channels:__"
           for channel_i in range(1, len(channels) + 1):
               message += "\n{0} - {1}".format(channel_i, channels[channel_i - 1])
        else:
            message = "No live stream channels have been set."
        
        await ctx.send(message)
  
    @commands.guild_only()
    @commands.command(aliases=['removeStream'])
    @checks.admin_or_permissions(manage_guild=True)
    async def removeLiveStream(self, ctx, url_or_id):
        """Removes live stream pages"""
        media_role = self.team_manager_cog._find_role_by_name(ctx, self.MEDIA_ROLE_STR)
        if not media_role or media_role not in ctx.message.author.roles:
            await ctx.send(":x: You must have the **{0}** role to run this command.".format(self.MEDIA_ROLE_STR))
            return False
        
        streams = await self._get_live_stream_channels(ctx.guild)
        url = await self._get_live_stream(ctx.guild, url_or_id)
        if url in streams:
            msg = "Remove \"__{0}__\" from list of stream pages?".format(url)
            react_msg = await ctx.send(msg)
            start_adding_reactions(react_msg, ReactionPredicate.YES_OR_NO_EMOJIS)
            try:
                pred = ReactionPredicate.yes_or_no(react_msg, ctx.message.author)
                await ctx.bot.wait_for("reaction_add", check=pred, timeout=verify_timeout)
                if pred.result:
                    await self._remove_live_stream_channel(ctx.guild, url)
                    await ctx.send("Done.")
                    return True
                else:
                    await ctx.send("\"__{0}__\" was not removed as a live stream page.".format(url))
            except asyncio.TimeoutError:
                await ctx.send("{0} You didn't react quick enough. Please try again.".format(ctx.author.mention))
        else:
            await ctx.send("Url not found: \"__{0}__\"".format(url))

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearLiveStreams(self, ctx, slot):
        """Removes all saved stream urls"""
        media_role = self.team_manager_cog._find_role_by_name(ctx, self.MEDIA_ROLE_STR)
        if not media_role or media_role not in ctx.message.author.roles:
            await ctx.send(":x: You must have the **{0}** role to run this command.".format(self.MEDIA_ROLE_STR))
            return False
        
        streams = await self._get_live_stream_channels(ctx.guild)
        if streams:
            msg = "Remove all saved live stream channels?"
            react_msg = await ctx.send(msg)
            start_adding_reactions(react_msg, ReactionPredicate.YES_OR_NO_EMOJIS)
            try:
                pred = ReactionPredicate.yes_or_no(react_msg, ctx.message.author)
                await ctx.bot.wait_for("reaction_add", check=pred, timeout=verify_timeout)
                if pred.result:
                    await self._save_live_stream_channels(ctx.guild, [])
                    await ctx.send("Done.")
                else:
                    await ctx.send("No live stream channels have been removed.")
            except asyncio.TimeoutError:
                await ctx.send("{0} You didn't react quick enough. Please try again.".format(ctx.author.mention))
        else:
            await ctx.send("No live stream channels found.")


    async def _get_stream_matches(self, ctx, live_stream, match_day):
        matches = []
        schedule = await self._stream_schedule(ctx.guild)
        for stream_page, match_days in schedule.items():
            if stream_page == live_stream:
                for this_match_day, time_slots in match_days.items():
                    if this_match_day == match_day:
                        for time_slot, match in sorted(time_slots.items()):
                            matches.append((time_slot, match))
        return matches

    async def _get_stream_match(self, ctx, match_day, team):
        schedule = await self._stream_schedule(ctx.guild)
        for stream_page, match_days in schedule.items():
            for this_match_day, time_slots in match_days.items():
                if this_match_day == match_day:
                    for time_slot, match in time_slots.items():
                        if match['home'].casefold() == team.casefold() or match['away'] == team.casefold():
                            return match, time_slot
        return None

    async def _add_application(self, ctx, requested_by, match_data, time_slot, requesting_team=None):
        applications = await self._applications(ctx.guild)
        app = await self._get_app_from_match(ctx.guild, match_data)
        if app and app['status'] != self.REJECTED_STATUS:
            await ctx.send(":x: Application is already in progress.")
            return False
        
        if not requesting_team:
            requesting_team = await self.team_manager_cog.get_current_team_name(ctx, requested_by)
        if match_data['home'].casefold() == requesting_team.casefold():
            other_team = match_data['away']
        else:
            other_team = match_data['home']

        other_franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, other_team)
        other_captain = await self.team_manager_cog._get_team_captain(ctx, other_franchise_role, tier_role)
        # send request to GM if team has no captain
        if not other_captain:
            other_captain = self.team_manager_cog._get_gm(ctx, other_franchise_role)

        new_payload = {
            "status": self.PENDING_OPP_CONFIRMATION_STATUS,
            "requested_by": requested_by.id,
            "request_recipient": other_captain.id,
            "home": match_data['home'],
            "away": match_data['away'],
            "slot": time_slot
        }
        
        # Possible improvement: Update match info instead of adding a new field/don't duplicate saved data/get match ID reference?
        # Add application
        try:
            applications[match_data['matchDay']].append(new_payload)
        except KeyError:
            applications[match_data['matchDay']] = [new_payload]
        
        await self._save_applications(ctx.guild, applications)

        # Challenge other team
        if self.team_manager_cog.is_gm(other_captain):
            message = gm_challenged_msg.format(match_day=match_data['matchDay'], home=match_data['home'], away=match_data['away'], time_slot=time_slot, channel=ctx.channel, gm_team=other_team)
        else:
            message = challenged_msg.format(match_day=match_day, home=match_data['home'], away=match_data['away'], time_slot=time_slot, channel=ctx.channel)
        await self._send_member_message(ctx, other_captain, message)
        return True

    async def _verify_gm_team(self, ctx, gm: discord.Member, team: str):
        franchise_role = self.team_manager_cog.get_current_franchise_role(gm)
        teams = await self.team_manager_cog._find_teams_for_franchise(ctx, franchise_role)
        for t in teams:
            if t.casefold() == team.casefold():
                return True
        await ctx.send(":x: **{0}** does not have a team named, **{1}**".format(franchise_role.name, team))
        return False

    async def _accept_reject_application(self, ctx, recipient, match_day, is_accepted, recipient_team=None):
        # request recipient responds to stream challenge
        applications = await self._applications(ctx.guild)

        if not recipient_team:
            recipient_team = await self.team_manager_cog.get_current_team_name(ctx, recipient)

        for app in applications[match_day]:
            if app['request_recipient'] == recipient.id:
                match_matches = app['home'].casefold() == recipient_team.casefold() or app['away'].casefold() == recipient_team.casefold()
                if app['status'] == self.PENDING_OPP_CONFIRMATION_STATUS and match_matches:
                    requesting_member = self._get_member_from_id(ctx.guild, app['requested_by'])
                    if is_accepted:
                        # Send update message to other team - initial requester and that team's captain
                        requesting_team = await self.team_manager_cog.get_current_team_name(ctx, requesting_member)
                        franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, requesting_team)
                        requesting_team_captain = await self.team_manager_cog._get_team_captain(ctx, franchise_role, tier_role)
                        
                        message = challenge_accepted_msg.format(match_day=match_day, home=app['home'], away=app['away'])
                        await self._send_member_message(ctx, requesting_member, message)
                        if requesting_team_captain and (requesting_member.id != requesting_team_captain.id):
                            await self._send_member_message(ctx, requesting_team_captain, message)
                        
                        # Send new complete app to media channel feed
                        stream_feed_channel = await self._stream_feed_channel(ctx)
                        if stream_feed_channel:
                            await stream_feed_channel.send("A new stream application has been submitted!")

                        # set status to pending league approval, save applications
                        app['status'] = self.PENDING_LEAGUE_APPROVAL_STATUS
                        await self._save_applications(ctx.guild, applications)
                        return True
                    else:
                        applications[match_day].remove(app)
                        await self._save_applications(ctx.guild, applications)
                        # Send rejection message to requesting player
                        message = challenge_rejected_msg.format(match_day=match_day, home=app['home'], away=app['away'])
                        await self._send_member_message(ctx, requesting_member, message)
                        return True
        return False

    async def _format_match_lobby_info(self, ctx, match_day, stream_url):
        media_role = self.team_manager_cog._find_role_by_name(ctx, self.MEDIA_ROLE_STR)
        
        title = "__Match Day {match_day}: {date}__".format(match_day=match_day, date="{date}")

        matchups = []
        lobby_names = []
        passwords = []

        matches = await self._get_stream_matches(ctx, stream_url, match_day)
        for match in matches:
            time_slot, match = match
            home = match['home']
            away = match['away']

            matchup = '{0} | {1} vs. {2}'.format(time_slot, home, away)
            match = await self.match_cog.get_match_from_day_team(ctx, match_day, home)
            if match:
                if '{date}' in title:
                    title = title.format(date=match['matchDate'])
                matchups.append(matchup)
                lobby_names.append(match['roomName'])
                passwords.append(match['roomPass'])

        if not matchups:
            return None

        # Format lobby info
        description = "Matchups and private lobby information for matches scheduled on stream"
        description += "\n\nLive Stream: " + stream_url
        embed = discord.Embed(title=title, description=description, color=media_role.color)
        embed.add_field(name="Matchup", value='{}\n'.format('\n'.join(matchups)), inline=True)
        embed.add_field(name="Room Name", value='{}\n'.format('\n'.join(lobby_names)), inline=True)
        embed.add_field(name="Room Password", value='{}\n'.format('\n'.join(passwords)), inline=True)
        return embed

    async def _format_apps(self, ctx, for_approval=False, match_day=None, time_slot=None):
        if for_approval:
            message = "> __All stream applications pending league approval:__"
        else:
            message = "> __All stream applications in progress:__"
        message += "\n> \n> **<time slot> | <home> vs. <away>**"

        if not for_approval:
            message += " `[<status>]`"

        count = 0
        applications = await self._applications(ctx.guild)
        for md, apps in applications.items():
            if apps:
                message += "\n> \n> **__Match Day {0}__**".format(md)
            for app in apps:
                if (md == match_day or not match_day) and (app['slot'] == time_slot or not time_slot):
                    if not for_approval or app['status'] == self.PENDING_LEAGUE_APPROVAL_STATUS:
                        message += "\n> {0} | {1} vs. {2}".format(app['slot'], app['home'], app['away'])
                        if not for_approval:
                            message += " `[{0}]`".format(app['status'])
                        count += 1
                if match_day:
                    break
        
        if not count:
            return None

        if for_approval:
            message += "\n> \n> -- \n> Use `{p}approveApp` or `{p}rejectApp` to approve/reject an application.".format(p=ctx.prefix)

        return message
    
    async def _remove_match_from_stream(self, ctx, match_day, team, notify_teams=True):
        schedule = await self._stream_schedule(ctx.guild)
        removed_match = False

        # Potential removal data types
        match_found = False
        time_slots = None
        match_days = None
        this_match_day = None

        # Find, Remove Match from Stream Schedule
        for stream_page, match_days in schedule.items():
            for this_match_day, time_slots in match_days.items():
                if this_match_day == match_day:
                    for time_slot, match in time_slots.items():
                        if match['home'].casefold() == team.casefold() or match['away'].casefold() == team.casefold():
                            match_found = True
                            break

        if match_found:
            removed_match = time_slots.pop(time_slot, None)
            if not time_slots:
                match_days.pop(this_match_day, None)
            if not match_days:
                schedule.pop(stream_page, None)
            await self._save_stream_schedule(ctx.guild, schedule)


        # Update Match in Match Cog
        if removed_match:
            await self.match_cog.remove_match_from_stream(ctx, match_day, team)
        else:
            return False

        # Update application status
        applications = await self._applications(ctx.guild)
        for this_match_day, apps in applications.items():
            if this_match_day == match_day:
                for app in apps:
                    if app['home'].casefold() == team.casefold() or app['away'].casefold() == team.casefold():
                        app['status'] = self.RESCINDED_STATUS
                        await self._save_applications(ctx.guild, applications)
                        break
        
        if not notify_teams:
            return removed_match
        
        # Don't notify if the match has already happened.
        current_match_day = await self.match_cog._match_day(ctx)
        if int(match_day) < int(current_match_day):
            return removed_match

        # Notify all team members that the game is no longer on stream
        message = rescinded_msg.format(match_day=match_day, home=removed_match['home'], away=removed_match['away'])
        for team in [removed_match['home'], removed_match['away']]:
            franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, team)
            gm, team_members = self.team_manager_cog.gm_and_members_from_team(ctx, franchise_role, tier_role)

            await self._send_member_message(ctx, gm, message)
            for team_member in team_members:
                await self._send_member_message(ctx, team_member, message)
        
        return match_found

    async def _schedule_match_on_stream(self, ctx, stream_channel, match_day, slot, home, away):
        already_scheduled = await self._get_stream_match(ctx, match_day, home)
        if already_scheduled:
            match, scheduled_slot = already_scheduled
            if scheduled_slot == slot:
                await ctx.send(":exclamation: This match is already scheduled for this time slot ({0}).".format(scheduled_slot))
            else:
                await ctx.send(":x: This match is already scheduled for time slot {0}.".format(scheduled_slot))
            return False
        
        schedule = await self._stream_schedule(ctx.guild)
        if schedule:
            try:
                conflict = schedule[stream_channel][match_day][slot]
                await ctx.send(":x: There is already a stream scheduled for this stream slot. ({0} vs. {1})".format(conflict['home'], conflict['away']))
                return False
            except KeyError:
                try:
                    schedule[stream_channel][match_day][slot] = {'home': home, 'away': away}
                except KeyError:
                    try:
                        schedule[stream_channel][match_day] = {slot: {'home': home, 'away': away}}
                    except KeyError:
                        schedule[stream_channel] = {match_day: {slot: {'home': home, 'away': away}}}  
        else:
            schedule = {stream_channel: {match_day: {slot: {'home': home, 'away': away}}}}
        scheduled = await self._save_stream_schedule(ctx.guild, schedule)
        
        if not scheduled:
            return False
        
        # Update match cog details
        stream_details = {
            'live_stream': stream_channel,
            'slot': slot,
            'time': await self._get_time_from_slot(ctx.guild, slot)
        }
        await self.match_cog.set_match_on_stream(ctx, match_day, home, stream_details)

        # Notify all team members that the game is on stream
        message = league_approved_msg.format(match_day=match_day, home=home, away=away, slot=slot, live_stream=stream_channel, channel=stream_channel)
        for team_name in [home, away]:
            franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, team_name)
            gm, team_members = self.team_manager_cog.gm_and_members_from_team(ctx, franchise_role, tier_role)

            await self._send_member_message(ctx, gm, message)
            for team_member in team_members:
                await self._send_member_message(ctx, team_member, message)
        
        return scheduled

    async def _stream_schedule(self, guild):
        return await self.config.guild(guild).Schedule()

    async def _save_stream_schedule(self, guild, schedule):
        await self.config.guild(guild).Schedule.set(schedule)
        return True

    async def _get_app(self, guild, match_day, team):
        team = team.casefold()
        for this_match_day, apps in (await self._applications(guild)).items():
            if this_match_day == match_day:
                for app in apps:
                    if app['home'].casefold() == team or app['away'].casefold() == team:
                        return app
        return None

    async def _get_app_from_match(self, guild, match):
        return await self._get_app(guild, match['matchDay'], match['home'])

    async def _applications(self, guild):
        return await self.config.guild(guild).Applications()

    async def _save_applications(self, guild, applications):
        await self.config.guild(guild).Applications.set(applications)

    async def _clear_applications(self, guild):
        await self.config.guild(guild).Applications.set({})
    
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

    async def _stream_feed_channel(self, ctx):
        return ctx.guild.get_channel(await self.config.guild(ctx.guild).StreamFeedChannel())

    async def _save_stream_feed_channel(self, ctx, stream_feed_channel):
        await self.config.guild(ctx.guild).TransChannel.set(stream_feed_channel)
    
    async def _get_time_from_slot(self, guild, slot):
        data = await self.config.guild(guild).TimeSlots()
        for s, t in data.items():
            if slot == s:
                return t
        return None

    async def _get_time_slots(self, guild):
        return await self.config.guild(guild).TimeSlots()

    async def _add_time_slot(self, guild, slot, time):
        data = await self.config.guild(guild).TimeSlots()
        data[slot] = time
        await self._save_time_slots(guild, data)
        return True

    async def _save_time_slots(self, guild, time_slots):
        await self.config.guild(guild).TimeSlots.set(time_slots)
    
    async def _get_live_stream(self, guild, url_or_id):
        channels = await self._get_live_stream_channels(guild)
        if url_or_id in channels:
            return url_or_id
        try:
            i = int(url_or_id)
            return channels[i - 1]
        except:
            return None
        return None

    async def _get_live_stream_channels(self, guild):
        return await self.config.guild(guild).LiveStreamChannels()

    async def _add_live_stream_channel(self, guild, url):
        channels = await self._get_live_stream_channels(guild)
        channels.append(url)
        return await self._save_live_stream_channels(guild, channels)
    
    async def _remove_live_stream_channel(self, guild, url):
        channels = await self._get_live_stream_channels(guild)
        channels.remove(url)
        return await self._save_live_stream_channels(guild, channels)

    async def _save_live_stream_channels(self, guild, urls):
        await self.config.guild(guild).LiveStreamChannels.set(urls)
        return True


challenged_msg = ("You have been asked to play **match day {match_day}** ({home} vs. {away}) on stream at **time slot {time_slot}**. "
    "Please respond to this request in the **#{channel}** channel with one of the following:"
    "\n\t - To accept: `[p]streamapp accept {match_day}`"
    "\n\t - To reject: `[p]streamapp reject {match_day}`"
    "\nThis stream application will not be considered until you respond.")

gm_challenged_msg = ("You have been asked to play **match day {match_day}** ({home} vs. {away}) on stream at **time slot {time_slot}**. "
    "Please respond to this request in the **#{channel}** channel with one of the following:"
    "\n\t - To accept: `[p]streamapp accept {match_day} {gm_team}`"
    "\n\t - To reject: `[p]streamapp reject {match_day} {gm_team}`"
    "\nThis stream application will not be considered until you respond.")

challenge_accepted_msg = (":white_check_mark: Your stream application for **match day {match_day}** ({home} vs. {away}) has been accepted by your opponents, and is "
    "now pending league approval. An additional message will be sent when a decision is made regarding this application.")

challenge_rejected_msg = (":x: Your stream application for **match day {match_day}** ({home} vs. {away}) has been rejected by your opponents, and will "
    "not be considered moving forward.")

league_approved_msg = ("**Congratulations!** You have been selected to play **match day {match_day}** ({home} vs. {away}) on stream at "
    "the **{slot} time slot**. You may use the `[p]match {match_day}` in your designated bot input channel see updated "
    "details of this match. We look forward to seeing you on the stream listed below!\n\nLive Stream Page: {live_stream}")

league_rejected_msg = ("Your application to play **match day {match_day}** ({home} vs. {away}) on stream has been denied. "
    "Your application will be kept on file in the event that an on-stream match has been rescheduled.")

rescinded_msg = ("Your match that was scheduled to be played on stream (Match Day {match_day}: **{home}** vs. **{away}**) has been **rescinded**. This match will no longer be played"
    "on stream, and will be played as it was originally scheduled. \n\nYou may use the `[p]match {match_day}` command to see your updated match information for match day {match_day}.")