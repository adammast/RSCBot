# RSCBot: combineRooms

The `combineRooms` cog is primarily responsible for managing combines for RSC. This involves dynamically creating and deleting voice channels under a "Combine Rooms" category. This cog uses discord events to keep rooms open for each tier that has been established.

## Installation

The `combineRooms` cog depends on the `teamManager` cog. Install `teamManager` as well as its dependencies before installing `combineRooms`.

```
<p>cog install RSCBot combineRooms
<p>load combineRooms
```

## Usage

- `<p>startcombines`
  Creates a Combine Rooms channel category with all associated text and voice channels.

- `<p>stopcombines`
  Runs a teardown for all combine channels. This will remove all channels under the "Combine Rooms" categorty as well as the category itself.

## Customization

- `<p>setPlayersPerRoom` (Default: 6)
  - Sets the reccomended concurrent FA/DE limit in a room.
  - (Disabled) The room name will reflect the number of FA/DE players in them
    - Naming format: `<Rank> room <room number> (<player count>/<players_per_room>)`
  - Examples:
    - 3v3 leagues should have no more than 6 Free Agent/Draft Eligible players combined.
    - 2v2 leagues should have no more than 4 Free Agent/Draft Eligible players combined.
    - Special case: RSC's 1v1 league will have rooms of 4 players, who will cycle through matches against each other player in the room.
- `<p>setRoomCapacity` (Default: 10)
  - Sets the limit for discord members in room. This limit is role agnostic.
  - This is a limit for players and scouts in a single room.
- `<p>togglePublicity` (Default: Public)
  - Toggles the combines between a Public and Private status.
  - If combines are Public, any member may participate.
  - If combines are Private, only members with the "League" role may particpate.
- `<p>setAcronym` (Default: RSC)
  - Sets the acronym used in the combines cog.
  - This is used to tweak the default message in the #combine-details channel, such as rule reference, and room information.
- `<p>setCombinesMessage <message>`
  - Sets a custom message that is sent to the #combines-details channel.
  - To change the combines message back to the default, run either of the following:
    - `<p>setCombinesMessage clear`
    - `<p>setCombinesMessage reset`

## Other commands

The following commands can be used to check current properties of the server:
- `<p>getPlayersPerRoom`
- `<p>getRoomCapacity`
- `<p>getCombinePublicity`
- `<p>getAcronym`
- `<p>getCombinesMessage`
