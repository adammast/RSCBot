# RSCBot: streamSignupManager

The `streamSignupManager` cog is primarily responsible for managing stream signups for RSC. This is used to manage which live stream channels are available for streams, and what time slots are available.

## Installation

The `streamSignupManager` cog depends on the `match` cog. Install `match` as well as its dependencies before installing `streamSignupManager`.

```
<p>cog install RSCBot streamSignupManager
<p>load streamSignupManager
```
### Roles

Franchise, Tier and General Manager roles must be defined for this cog to work properly. In addition, some commands are limited to users who have a **Media Committee** role.

## Usage

Team players may initiate stream applications for any of their scheduled match games. This alerts the captain of the team they will face for that match night. The opposting team captain will be prompted to either accept or reject that command. Upon their response, the player who initated the application is informed of how they responded. If they agreed, the Media Committee will be notified that a new application has been completed if a streamFeedChannel has been set.

Media Committee members may accept or reject applications, or rescind applications that hve already been approved. Media Committee members may also bypass the application process entirely and set a match to be on stream directly. In any of these events, all players will be informed of the decision.

When a match has been set to be on stream, the `<p>match` command in the match cog will behave differently to reflect important information around playing their match on stream.

- `<p>streamApp <action> <match_day> <time_slot> <team>`
    - Central command for managing stream signups. This is used to initiate stream applications, as well as accepting/rejecting requests to play on stream.
    - Note: The team parameter is ignored if you are not a General Manager.
    - action keywords: apply, accept, reject
    - **Examples:**
        - `<p>streamApp apply 1 1`
        - `<p>streamApp accept 3`
        - `<p>stream reject 3`
    - Note: If you are a **General Manager**, you must include the team name in applications
        - `<p>streamApp apply 1 1 Spartans`
        - `<p>streamApp accept 4 Vikings`
        - `<p>streamApp reject 3 Vikings`
- `<p>reviewApps [match_day] [time_slots]`
    - View all completed stream applications that are pending league approval. Match Day and Time Slot filters are optional.
    - Note: Media Committee only
- `<p>allApps [match_day] [time_slots]`
    - View all stream applications and their corresponding statuses. This is largely used for debugging purposes.
    - Note: Media Committee only
- `<p>clearApps`
    - Clears all saved applications.
    - Note: Media Committee only
- `<p>approveApp <url_or_id> <match_day> <team>`
    - Approve application for stream.
    - Applications that have `PENDING_LEAUGE_APPROVAL`, `REJECTED`, or `RESCINDED` status may be approved.
    - Note: Media Committee only
- `<p>rejectApp <match_day> <team>`
    - Reject application for stream
    - Note: Media Committee only
- `<p>setMatchOnStream <url_or_id> <match_day> <team>`
    - Override application process and set match on stream
    - **Examples:**
        - `<p>setMatchOnStream 1 1 1 Spartans`
        - `<p>setMatchOnStream https://twitch.tv/rocketsoccarconfederation 2 8 Vikings`
    - Note: Media Committee only
- `<p>streamSchedule [url_or_id] [match_day]`
    - View Matches that have been scheduled on stream
    - `<p>streamSchedule today` may be used to see the schedule for the current week's stream matches.
- `<p>getStreamLobbies [url_or_id] [match_day]`
    - Get Private Lobby information for matches that will be scheduled on stream. Private lobby information will be sent as an embed in DMs.
    - If `url_or_id` is not provided, information will be sent for all found stream channels with matches scheduled.
    - If `match_day` is not provided, information will be sent for current match day.
    - Note: Media Committee only
- `<p>clearStreamSchedule`
    - Removes stream schedule
    - Note: This will **not** update information in the match cog.
    - Note: Media Committee only
- `<p>rescindStreamMatch <match_day> <team>`
    - Removes a match from the stream schedule
    - Note: Media Committee only
- `<p>setStreamFeedChannel <channel>`
    - Sets the channel where all stream application notification messages will be posted
    - Note: Media Committee only
- `<p>getStreamFeedChannel`
    - Gets the channel currently assigned as the stream feed channel. Stream application updates are sent to this channel when it is set.
- `<p>unsetStreamFeedChannel`
    - Unsets the stream feed channel.
    - Note: Media Committee only
- `<p>addTimeSlot <slot> <time>`
    - Adds a time slot association
    - Note: Media Committee only
- `<p>getTimeSlots`
    - Lists all registered live stream time slots
- `<p>removeTimeSlot <slot>`
    - Lists all registered live stream time slots
    - Note: Media Committee only
- `<p>clearTimeSlots`
    - Removes all time slot associations
    - Note: Media Committee only
- `<p>addLiveStream <url>`
    - Adds a new live stream page for stream signups
    - Note: Media Committee only
- `<p>getLiveStreams`
    - Lists all saved live stream channels
    - Note: Media Committee only
- `<p>removeLiveStream <url_or_id>`
    - Removes live stream pages
    - Note: Media Committee only
- `<p>clearLiveStreams <slot>`
    - Removes all saved stream urls
    - Note: Media Committee only


## Customization

The following items may be customized with commands listed above:
 - Update Channel Feed for stream application notifications/alerts
 - Live Streams Channels that will be available for stream signups
 - Time slots available for each match night
