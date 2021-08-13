# RSCBot: modLink

The `modLink` cog is responsible for maintaining member status and representation consistency across multiple discord guilds. This cog processes member updates and applies them to each guild in the `modLink` network. This is defined by guilds the RSCBot is in, that have set an Event Log Channel.

This cog also tracks recent member joins for bot detection, and will take action against joined members who are flagged as potentially malicious bot accounts.

## Installation

The `modLink` cog is independent from other RSCBot cogs.

```
<p>cog install RSCBot modLink
<p>load modLink
```

# Cross-Server Management

The following behaviors are shared across the guild network:

- Shared role addition and removal (Default: [**"Muted"**])
- Member bans and unbans.
- Nickname changes (not including prefixes, or awards)

An event log channel must be set in order to enable cross-server user management.

- `<p>setEventChannel [event_channel]`
  Sets the channel where all moderator-link related events are logged, and enables cross-guild member updates
- `<p>unsetEventChannel`
  Unsets the channel currently assigned as the event log channel and disables cross-guild member updates
- `<p>getEventChannel`
  Gets the channel currently assigned as the event log channel

# Nickname Updates

This cog has a number of commands for nickname management as it pertains to league awards.

- `<p>addTrophy [userList]`
  Adds a **Trophy** emoji to each user passed in the userList
- `<p>addMedal [userList]`
  Adds a **First Place** medal to each user passed in the userList
- `<p>addStar [userList]`
  Adds a **Star** emoji to each member passed in the userlist to designate them as an All-Star.
- `<p>clearAllStars`
  Removes the **Star** emojis from each member in the guild who has them.

# Bot Detection

Bot Detection tracks for bots disguised as user accounts and takes action when a recently joined member is detected as a bot.

Members who are flagged as bots are sent a message to let them know they have been flagged as a bot account. This message contains a new invite link and informs kicked users to send a message to the guild owner if the issue persists. Afterwards, the member is kicked from the server. These events are logged in the event log channel if one is set.

If a member is falsely flagged as a bot, an admin or mod may whitelist them by their discord ID, and they will bypass bot detection.

## Ban Conditions

For a user to be flagged as a potentially malicous bot account, and banned from the guild, the member's id must not be on the whitelist, and one of two conditions must be met upon the member join:

- The username associated with the member is the same as another member who joined within the last five (5) minutes.
- The member's account is less than approximately 24 hours old, and a subset of their name appears in the username blacklist.

## Commands

- `<p>toggleBotDetection`
  Enables or disables **Bot Detection and Protection** for the guild.

- `<p>getRecentJoins`
  Displays members who have joined in the past five minutes. These members are tracked to prevent spammed bot joins.
- `<p>whitelistUser <user_id>`
  Adds a user (by discord ID) to the user whitelist. Whitelisted users will bypass member bot detection.
- `<p>getUserWhitelist`
  Displays all whitelisted user IDs
- `<p>unwhitelistUser <user_id>`
  Removes a user from the user whitelist.
- `<p>getBlacklistedNames`
  Gets all blacklisted member names. **Note:** Blacklisted names are only banned if their account is less than ~24 hours old.
- `<p>blacklistName <name>`
  Adds a new name to the username blacklist.
- `<p>unblacklistName <name>`
  Removes a name from the username blacklist.
