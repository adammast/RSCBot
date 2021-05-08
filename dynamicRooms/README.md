# RSCBot: dynamicRooms

The `dynamicRooms` cog is primarily responsible for enabling automatic voice channel management in accordance with member behavior and guild interaction. This cog enables automatic room generation and deletion as well as configuration for "hideout rooms."

## Installation

The `dynamicRooms` cog is independant from all other cogs. No prerequisites are required.

```
<p>cog install RSCBot dynamicRooms
<p>load dynamicRooms
```

## Standard Commands

- `<p>hide`
  Hides the voice channel the invoker currently occupies from other members in the guild.

## Admin Settings

- `<p>addDynamicCategory`
  Sets all voice channels contained by a category to become dynamic voice channels. When a member joins an empty dynamic room, the room is cloned, and the populated voice channel is moved to the bottom of the category. When all members leave a dynamic room, the voice channel is terminated.
- `<p>getDynamicCategories`
  Lists all Categories that have been set as dynamic.
- `<p>clearDynamicCategories`
  Disables dynamic behavior of a given category.
- `<p>addDynamicRoom`
  Sets a voice channel to be dynamic. This is independent from a dynamic category.
- `<p>getDynamicRooms`
  View all individiual voice channels that are configured for dynamic room management.
- `<p>clearDynamicRooms`
  Disables dynamic room behavior of individual dynamic rooms.
- `<p>addHideoutCategory`
  Sets existing category where each contained voice channel will be cloned and hidden when it reaches its capacity.
- `<p>clearHideoutCategories`
  Disables hideout room behavior of all hideout categories.
- `<p>getHideoutCategories`
  View all categories that are configured for hideout room management.
- `<p>getHiddenRooms`
  View all individiual voice channels that are actively hidden.
- `<p>clearDynamicVCData`
  Clears all dynamic room data in the `dynamicRooms` cog
- `<p>toggleHideoutVCs`
  Enables or disables the `<p>hide command`.
