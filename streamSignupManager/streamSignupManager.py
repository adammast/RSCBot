import re
import discord
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions

defaults = {"Applications": {}, "Schedule": {}, "TimeSlots": {}, "LiveStreamChannels": [], "StreamFeedChannel": None}
verify_timeout = 30

# TODO: (All listed todos)
# + league approve/reject applications
# + alert all game players when match has been league approved, include which stream its on
# + reject applications for same time frame/alert that a different application has been accepted.

# Roles: Captain, GM, <Tier>, <Franchise>, (Soon: Stream Committee)

class StreamSignupManager(commands.Cog):
    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567892, force_registration=True)
        self.config.register_guild(**defaults)
        self.match_cog = bot.get_cog("Match")
        self.team_manager_cog = bot.get_cog("TeamManager")
        self.bot = bot

        # Application statuses
        self.PENDING_OPP_CONFIRMATION_STATUS = "PENDING_OPP_CONFIRMATION"
        self.PENDING_LEAGUE_APPROVAL_STATUS = "PENDING_LEAGUE_APPROVAL"
        self.SCHEDULED_ON_STREAM_STATUS = "SCHEDULED_ON_STREAM"
        self.REJECTED_STATUS = "REJECTED"
    
    @commands.command(aliases=["streamapp", "streamapply", "streamApplications", "streamapplications"])
    @commands.guild_only()
    async def streamApp(self, ctx, action, match_day, time_slot=None, team=None):
        """
        Central command for managing stream signups. This is used to initiate stream applications, as well as accepting/rejecting requests to play on stream.

        The team parameter is ignored if you are not a General Manager.

        **action keywords:** apply, accept, reject
        
        **Examples:**
        [p]streamApp apply 1 1
        [p]streamApp accept 3
        [p]stream reject 3

        Note: If you are a **General Manager**, you must include the team name in applications
        [p]streamApp apply 1 1 Spartans
        [p]streamApp accept 4 Vikings
        [p]streamApp reject 3 Vikings
        """

        requesting_member = ctx.message.author
        gm_role = self.team_manager_cog._find_role_by_name(ctx, self.team_manager_cog.GM_ROLE)
        if gm_role in requesting_member.roles:
            requesting_team = team
            if action == 'apply':
                if not requesting_team:
                    await ctx.send(":x: GMs must include the team name in their streamApp commands.")
                    return False
            elif action in ['accept', 'reject'] and team == None:
                requesting_team = time_slot  # shift param places for when GMs respond to apps
            if not await self._verify_gm_team(ctx, requesting_member, requesting_team):
                return False
        else:
            requesting_team = await team_manager_cog.get_current_team_name(ctx, requesting_member)

        if action == "apply":
            if not time_slot:
                await ctx.send(":x: stream slot must be included in an application.")
                return False
            match = await self.match_cog.get_match_from_day_team(ctx, match_day, requesting_team)
            if not match:
                await ctx.send("No match found for {team} on match day {match_day}".format(team=requesting_team, match_day=match_day))
            
            if not await self._get_time_from_slot(ctx.guild, slot):
                await ctx.send(":x: {0} is not a valid time slot".format(slot))
                return False
            
            applied = await self._add_application(ctx, requesting_member, match, time_slot, requesting_team)
            if applied:
                await ctx.send("Done.")
                return True
            else:
                return False
        if action not in ["accept", "reject"]:
            await ctx.send("\"{0}\" is not a recognized action. Please either _accept_ or _reject_ the stream application.".format(action))
            return False

        accepted = True if action == "accept" else False
        if gm_role in requesting_member.roles:
            updated = await self._accept_reject_application(ctx, ctx.author, match_day, accepted, requesting_team)
        else:
            updated = await self._accept_reject_application(ctx.guild, ctx.author, match_day, accepted)
        
        if updated:
            if accepted:
                await ctx.send("Your application to play match day {0} on stream has been updated.".format(match_day))
                return True
            else:
                await ctx.send("You have denied your application to play match day {0} on stream.".format(match_day))
                return True
        else:
            await ctx.send(":x: Stream Application not found.")

    @commands.command(aliases=['clearapps', 'removeapps'])
    @commands.guild_only()
    async def clearApps(self, ctx):
        """Clears all saved applications."""
        await self._clear_applications(ctx.guild)
        await ctx.send("Done.")

    @commands.command(aliases=['apps', 'reviewapps', 'reviewApplications'])
    @commands.guild_only()
    async def reviewApps(self, ctx, match_day=None, time_slot=None):
        """
        View all completed stream applications that are pending league approval. Match Day and Time Slot filters are optional.
        """
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
        View all stream applications and their corresponding statuses. Match Day and Time Slot filters are optional.
        """
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

    @commands.command()
    @commands.guild_only()
    async def streamSchedule(self, ctx, url_or_id=None, match_day=None):
        """View Matches that have been scheduled on stream"""
        schedule = await self._stream_schedule(ctx.guild)
        url = await self._get_live_stream(ctx.guild, url_or_id)

        if url:
            message = "Stream Schedule for \"__{0}__\"".format(url)
            if match_day:
                message += " (match day {0})".format(match_day)
        else:
            message = "Stream Schedule"
        message += ":\n"
        
        # Print Quoted Schedule
        num_matches = 0
        for this_url, match_days in schedule.items():
            if url == this_url or not url:
                message += "\n> \n> __**{0} Schedule**__".format(this_url)
                if match_day == this_match_day or not match_day:
                    for this_match_day, time_slots in sorted(match_days.items()):
                        message += "\n> __Match Day {0}__".format(this_match_day)
                            for time_slot, match in sorted(time_slots.items()):
                                message += "\n> {0} | {1} vs. {2}".format(time_slot, match['home'], match['away'])
                                num_matches += 1
        if not num_matches:
            message = ":x: No matches have been scheduled"
            if not url and match_day:
                message = ":x: \"{0}\" is not a valid url or live stream id"
            else:
                if match_day:
                    message += " for match day {0}".format(match_day)
                if url:
                    message += " on {0}".format(url)
            message += "."
            
        await ctx.send(message)

    @commands.command()
    @commands.guild_only()
    async def approveApp(self, ctx, match_day, url_or_id, team):
        """Approve application for stream"""
        apps = await self._applications(ctx.guild)
        stream_channel = self._get_live_stream(ctx.guild, url_or_id)
        if not stream_channel:
            ctx.send("\"__{url}__\" is not a valid url or id association. Use `{p}getLiveStreams` to see registered live stream pages.".format(url=url_or_id, p=ctx.prefix))
        for app in apps[match_day]:
            if app['home'] == team or app['away'] == team:
                # Update App Status
                app['status'] = self.SCHEDULED_ON_STREAM_STATUS

                # Add to Stream Schedule
                schedule = await self._stream_schedule(ctx.guild)
                try:
                    conflict = schedule[stream_channel][match_day][slot]
                    await ctx.send("There is already a stream scheduled for this stream slot. ({0} vs. {1})".format(conflict['home'], conflict['away']))
                except KeyError:
                    schedule[stream_channel][match_day][slot] = {'home': app['home'], 'away': app['away']}
                
                scheduled = await self._save_stream_schedule(ctx.guild, schedule)
                if not scheduled:
                    return False
                
                await self._save_applications(ctx.guild, apps)
                
                # Update match cog details
                stream_details = {
                    'channel': stream_channel,
                    'slot': app['slot'],
                    'time': await self._get_time_from_slot(ctx.guild, slot)
                }
                await self.match_cog.set_match_on_stream(ctx, match_day, team, stream_details)

                # Notify all team members that the game is on stream
                message = league_approved_msg.format(match_day=match_day, home=app['home'], away=app['away'], slot=slot, live_stream=stream_channel)
                for team_name in [app['home'], app['away']]:
                    franchise_role, tier_role = await self._roles_for_team(ctx, team_name)
                    gm, team_members = self.gm_and_members_from_team(ctx, franchise_role, tier_role)

                    await gm.send(message)
                    for team_member in team_members:
                        await team_member.send(message)

                await ctx.send("Done.")
                return True

        await ctx.send("Stream Application could not be found.")
          
    @commands.command()
    @commands.guild_only()
    async def rejectApp(self, ctx, match_day, team):
        """Reject application for stream"""
        apps = await self._applications(ctx.guild)
        stream_channel = self._get_live_stream(ctx.guild, url_or_id)
        for app in apps[match_day]:
            if app['home'] == team or app['away'] == team:
                # Update App Status
                app['status'] = self.REJECTED_STATUS
                await self._save_applications(ctx.guild, apps)

                # Inform applicants that their application has been rejected
                message = league_rejected_msg.format(match_day=match_day, home=app['home'], away=app['away'])
                for member_id in [app['requested_by'], app['request_recipient']]:
                    member = await self._get_member_from_id(ctx.guild, member_id)
            
                await ctx.send("Done.")
                return True
        await ctx.send(":x: Stream Application could not be found.")
    
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
        if await self._get_time_from_slot(ctx.guild, slot):
            await ctx.send(":x: Time slot {0} is already registered.".format(slot))
            return False
        await self._add_time_slot(ctx.guild, slot, time)
        await ctx.send("Done.")

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def removeTimeSlot(self, ctx, slot):
        """Remove time slot association"""
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
        await self._save_time_slots(ctx.guild, {})
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
    @commands.command(aliases=['addStream'])
    @checks.admin_or_permissions(manage_guild=True)
    async def addLiveStream(self, ctx, url):
        """Adds a new live stream page for stream signups"""

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
        except:
            await ctx.send("{0} You didn't react quick enough. Please try again.".format(ctx.author.mention))
        
    @commands.guild_only()
    @commands.command(aliases=['removeStream'])
    @checks.admin_or_permissions(manage_guild=True)
    async def removeLiveStream(self, ctx, url_or_id):
        """Removes live stream pages"""
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
            except:
                await ctx.send("{0} You didn't react quick enough. Please try again.".format(ctx.author.mention))
        else:
            await ctx.send("Url not found: \"__{0}__\"".format(url))

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearLiveStreams(self, ctx, slot):
        """Removes all saved stream urls"""
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
            except:
                await ctx.send("{0} You didn't react quick enough. Please try again.".format(ctx.author.mention))
        else:
            await ctx.send("No live stream channels found.")


    async def _add_application(self, ctx, requested_by, match_data, time_slot, requesting_team=None):
        applications = await self._applications(ctx.guild)
        if await self._get_app_from_match(ctx.guild, match_data):
            await ctx.send(":x: Application is already in progress.")
            return False
        
        if not requesting_team:
            requesting_team = await self.team_manager_cog.get_current_team_name(ctx, requested_by)
        if match_data['home'] == requesting_team:
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
        try:
            franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, team)
            if franchise_role not in gm.roles:
                await ctx.send(":x: The team **{0}** does not belong to the franchise, **{1}**.".format(team, franchise_role.name))
                return False
            return True
        except LookupError:
            await ctx.send(":x: {0} is not a valid team name".format(team))
            return False

    async def _accept_reject_application(self, ctx, recipient, match_day, is_accepted, responding_team=None):
        applications = await self._applications(ctx.guild)
        if responding_team:
            gm_team_match = False
        else:
            gm_team_match = True

        for app in applications[match_day]:
            if app['request_recipient'] == recipient.id:
                if responding_team:
                    if app['home'] == responding_team or app['away'] == responding_team:
                        gm_team_match = True
                if app['status'] == self.PENDING_OPP_CONFIRMATION_STATUS and gm_team_match:
                    requesting_member = self._get_member_from_id(ctx.guild, app['requested_by'])
                    if is_accepted:
                        # Send update message to other team - initial requester and that team's captain
                        if not responding_team:
                            responding_team = await self.team_manager_cog.get_current_team_name(ctx, requesting_member)
                        franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, responding_team)
                        other_captain = await self.team_manager_cog._get_team_captain(ctx, franchise_role, tier_role)
                        
                        message = challenge_accepted_msg.format(match_day=match_day, home=app['home'], away=app['away'])
                        await self._send_member_message(ctx, requesting_member, message)
                        if other_captain and requesting_member.id != other_captain.id:
                            await self._send_member_message(ctx, requesting_member, message)
                        
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
                        await self._save_applications(guild, applications)
                        # Send rejection message to requesting player
                        message = challenge_rejected_msg.format(match_day=match_day, home=app['home'], away=app['away'])
                        await self._send_member_message(ctx, requesting_member, message)
                        return True
        return False

    async def _format_apps(self, ctx, for_approval=False, match_day=None, time_slot=None):
        if for_approval:
            message = "> __All stream applications pending league approval:__"
        else:
            message = "> __All stream applications in progress:__"
        message += "\n> \n> **<time slot> | <home> vs. <away>**"

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
        
    async def _stream_schedule(self, guild):
        return await self.config.guild(guild).Schedule()

    async def _save_stream_schedule(self, guild, schedule):
        await self.config.guild(guild).Schedule.set(schedule)
        return True

    async def _get_app(self, guild, match_day, team):
        for match_day, apps in (await self._applications(guild)).items():
            if match_day == match['matchDay']:
                for app in apps:
                    if app['home'] == team or app['away'] == team:
                        return app
        return None

    async def _get_app_from_match(self, guild, match):
        return self._get_app(guild, match['matchDay'], match['home'])

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
        try:
            i = int(url_or_id)
            return channels[i - 1]
        except IndexError:
            return None
        except ValueError:
            if url_or_id in channels:
                return url_or_id
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
    "the **{slot} time slot**. Feel free to use the `[p]match {match_day}` in your designated bot input channel see updated "
    "details of this match. We look forward to seeing you on the stream listed below!\n\nLive Stream Page: {live_stream}")

league_rejected_msg = ("Your application to play **match day {match_day}** ({home} vs. {away}) on stream has been denied. "
    "Your application will be kept on file in the event that an on-stream match has been rescheduled.")

