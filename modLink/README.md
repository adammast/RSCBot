# RSCBot: modLink

## About modLink

The `modLink` cog is responsible for maintaining member status and representation consistency across multiple discord guilds. This cog processes member updates and applies them to each guild in the `modLink` network. This is defined by guilds the RSCBot is in, that have set an Event Log Channel.

The following behaviors are shared across the guild network:

- Shared role addition and removal (Default: ["Muted"])
- Member bans and unbans.
- Nickname changes

## Installation

The `modLink` cog is independent from other RSCBot cogs.

```
<p>cog install RSCBot modLink
<p>load modLink
```

# Cross-Server Management

- `<p>setEventChannel [event_channel]`
  Sets the channel where all moderator-link related events are logged, and enables cross-guild member updates
- `<p>unsetEventChannel`
  Unsets the channel currently assigned as the event log channel and disables cross-guild member updates
- `<p>getEventChannel`
  Gets the channel currently assigned as the event log channel

# Nickname Updates

- `<p>addTrophy [userList]`
  Adds a medal to each user passed in the userList
- `<p>addMedal [userList]`
  Adds a first place medal to each user passed in the userList
