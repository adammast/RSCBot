# RSCBot: combineRooms

The `combineRooms` cog is primarily responsible for managing combines for RSC. This involves dynamically creating and deleting voice channels under a "Combine Rooms" category. This cog uses discord events to keep rooms open for each tier that has been established.

## Installation

The `combineRooms` cog depends on the `teamManager` cog. Install `teamManager` as well as its dependencies before installing `combineRooms`.

```
<p>cog install RSCBot combineRooms
<p>load combineRooms
```

## Usage

- `<p>startCombines`
  Creates a Combine Rooms channel category with all associated text and voice channels.

- `<p>stopCombines`
  Runs a teardown for all combine channels. This will remove all channels under the "Combine Rooms" categorty as well as the category itself.

#### Roles involved:
- League
- Muted

## Customization

- `<p>setRoomCapacity` (Default: 10)
  - Sets the limit for discord members in room.
- `<p>togglePublicity` (Default: Public)
  - Toggles the combines between a Public and Private status.
  - If combines are Public, any member may participate.
  - If combines are Private, only members with the "League" role may particpate.
- `<p>setAcronym` (Default: RSC)
  - Sets the acronym used in the combines cog.
  - This is is relevant with the naming scheme for dynamically created voice channels.

## Other commands

The following commands can be used to check current properties of the server:
- `<p>getRoomCapacity`
- `<p>getCombinePublicity`
- `<p>getAcronym`
