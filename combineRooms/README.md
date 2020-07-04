# RSCBot: combineRooms

The `combineRooms` cog is primarily responsible for managing combines for RSC. This involves dynamically creating and deleting voice channels under a "Combine Rooms" category. This cog uses discord events to keep rooms open for each tier that has been established.

## Installation

The `combineRooms` cog depends on the `teamManager` cog. Install `teamManager` as well as its dependencies before installing `combineRooms`.

```
<p>cog install RSCBot combineRooms
```

## Usage

- `<p>combines`
Its that simple! This command behaves as a switch. If a combines category exists, it will run a teardown of all the rooms. If there is not a combines category established, it will create one, and add a voice channel for each tier.

- `<p>combines [keywords]`
The `keywords` parameter can be used to force the start/stop behavior with the following keywords:
- Start combines keywords: start, create
- Stop combines keywords: stop, teardown, end

## Customization

- `<p>set_players_per_room` (Default 6)
    - Sets the reccomended concurrent FA/DE limit in a room.
    - (Disabled) The room name will reflect the number of FA/DE players in them
        - Naming format: `<Rank> room <room number> (<player count>/<players_per_room>)`
    - Examples:
        - 3v3 leagues should have no more than 6 Free Agent/Draft Eligible players combined.
        - 2v2 leagues should have no more than 4 Free Agent/Draft Eligible players combined.
        - Special case: RSC's 1v1 league will have rooms of 4 players, who will cycle through matches against each other player in the room.
- `<p>set_room_capacity` (Default 10)
    - Sets the limit for discord members in room. This limit is role agnostic.
    - This is a limit for players and scouts in a single room.
