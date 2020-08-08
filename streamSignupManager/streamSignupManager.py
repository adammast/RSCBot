import re
import discord
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks

defaults = {"Applications": []}

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
        applications = await self._get_applications(ctx.guild)
        message = "Pending applications ({}):".format(len(applications))
        if applications:
            for app in applications:
                message += "\nMD {0}: {1} vs. {2} at {3} (Status: {4})".format(
                    app['match_day'],
                    app['requested_by'],
                    app['request_recipient'],
                    app['time_slot'],
                    app['status']
                )
            await ctx.send(message)
            return True
        await ctx.send("\n{0}\n\t(None)".format(message))
        return False


    @commands.command(aliases=["streamapply", "afs"])
    @commands.guild_only()
    async def applyForStream(self, ctx, match_day, time_slot):
        requesting_member = ctx.message.author
        other_captain = requesting_member # TODO: get actual other captain
        await self._add_application(ctx.guild, requesting_member, other_captain, match_day, time_slot)

        message = ("You have been asked to play **match day {0}** on stream at the **{1} time slot**. "
        "Please respond to this request in the **#{2}** channel in the **{3}** server with one of the following:"
        "\n\t - To accept: `[p]streamapp accept {0}`"
        "\n\t - To reject: `[p]streamapp reject {0}`"
        "\nThis stream application will not be considered until you respond.").format(match_day, time_slot, ctx.channel, ctx.guild)
        await self._send_member_message(ctx, other_captain, message)

    @commands.command(aliases=["streamApplications"])
    @commands.guild_only()
    async def streamapp(self, ctx, action, match_day):
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
        
        await ctx.send("Stream Application not found.")

    @commands.command(aliases=['clearapps', 'removeapps'])
    @commands.guild_only()
    async def clearApps(self, ctx):
        await self._clear_applications(ctx.guild)
        await ctx.send("Done.")

    # Possibly remove
    @commands.Cog.listener("on_raw_reaction_add")
    async def on_raw_reaction_add(self, payload):
        return False
        channel_id = payload.channel_id
        member = payload.member
        emoji = payload.emoji
        user_id = payload.user_id
        message_id = payload.message_id
        event_type = payload.event_type

        # status_updated = await self._maybe_update_app_status(message_id, "APPLICATION_CONFIRMED")
        status_updated = False # TODO: update here
        if status_updated:
            application = await self._get_application(message_id)
            requested_by = application['requested_by']
            request_recipient = application['request_recipient']
            message = "Your application to play match day {0} on stream has been confirmed by {1}.".format(
                application['match_day'],
                application['request_recipient']
            )

    # Possibly remove
    @commands.Cog.listener("on_message")
    async def on_message(self, message):
        return False
        if str(message.channel) == "Direct Message with {0}".format(message.author):  
            messages = await message.channel.history(limit=2).flatten()
            
            for m in messages:
                if m.id == message.id:
                    messages.remove(m)
            
            
            ##
            guild = None
            application = None
            guild_ids = await self.config.all_guilds()
            for guild_id in guild_ids:
                print(guild_id)
                guild = await self.config.guild_from_id(guild_id)
                # application = self._get_application(guild, message_id)
                # if application:
                #     break
            ##

            if not application:
                return False

            verification = (
                application['message_id'] == messages[0].id
                and re.match(r'^((we|i)\saccept|accepted)', message.content.lower())
            )

            if verification:
                await message.author.send("I see you've accepted. Very good.")
                # self.config.member_from_ids(guild_id, member_id)
                

    async def _add_application(self, guild, requested_by, request_recipient, match_day, time_slot):
        #TODO: avoid duplicate applications
        applications = await self._get_applications(guild)
        match = await self.match_cog.get_match_from_day_team(ctx, match_day, team_name):
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
            "home_team": match['home'],
            "away_team": match['away'],
            "match_day": match_day,
            "time_slot": time_slot
        }
        #Possible improvement: Update match info instead of adding a new field/don't duplicate saved data/get match ID reference?
        applications.append(new_payload)
        await self._save_applications(guild, applications)

    # Not used
    async def _maybe_get_application(self, guild, message_id):
        found = False
        # if guild in self.config:
        #     if guild == key:
        #         found = True
        #         break
        if not found:
            return None
        return None



        applications = await self.config.guild(guild).Applications
        for application in applications:
            if application.message_id == message_id:
                return application
        return None
    
    async def _update_application(self, guild, recipient, match_day, is_accepted):
        applications = self._get_applications(guild)
        for app in applications:
            if app['request_recipient'] == recipient.id and app['match_day'] == match_day:
                if app['status'] == "PENDING_OPP_CONFIRMATION":
                    if is_accepted:
                        app['status'] == "PENDING_LEAGUE_APPROVAL"
                        await self._save_applications(guild, applications)
                        # TODO: send update to requesting player
                        return True
                    else:
                        applications.remove(app)
                        await self._save_applications(guild, applications)
                        # TODO: send rejection message to requesting player
                        return True
        return False

    async def _get_applications(self, guild):
        return await self.config.guild(guild).Applications()

    # TODO: remove this
    async def _maybe_update_app_status(self, message_id, status):
        applications = await self.config.guild(ctx.guild).Applications
        for application in applications:
            if application.message_id == message_id:
                application['status'] = status
                return True
        return False

    async def _save_applications(self, guild, applications):
        await self.config.guild(guild).Applications.set(applications)

    async def _clear_applications(self, guild):
        await self.config.guild(guild).Applications.set([])
    
    async def _send_member_message(self, ctx, member, message):
        message_title = "**Message from {0}:**\n\n".format(ctx.guild.name)
        message = message.replace('[p]', ctx.prefix)
        message = message_title + message
        return await member.send(message)