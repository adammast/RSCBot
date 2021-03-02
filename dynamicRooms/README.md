# RSCBot: dynamicRooms

The `dynamicRooms` cog is primarily responsible for enabling automatic voice channel management based server usage. This involves dynamically creating and deleting voice channels under a set category.

## Installation

The `dynamicRooms` cog is independant from all other cogs. No prerequisites are required.

```
<p>cog install RSCBot dynamicRooms
<p>load dynamicRooms
```

## Usage

- `<p>addDynamicCategory`
  Sets all voice channels contained by a category to become dynamic voice channels. When a member joins an empty dynamic room, the room is cloned, and the populated voice channel is moved to the bottom of the category. When all members leave a dynamic room, the voice channel is terminated.
- `<p>getDynamicCategories`
  Lists all Categories that have been set as dynamic.
- `<p>clearDynamicCategories`
  Disables dynamic behavior of a given category
