# RSCBot: prefixManager

The `prefixManager` cog is primarily responsible for creating and managing prefixes for RSC franchises. Prefixes are an essential piece of the RSCBot codebase.

Every franchise must have both, a prefix and a discord role in the appropriate format ([<franchise_name> (<GM_name>)](https://media.discordapp.net/attachments/679698891129880580/707975741505273938/Capture.PNG)) to be recognized properly. Each GM (General Manager) is the core dependency of the franchise.

## Installation

The `prefixManager` has no other cog dependancies.

```
<p>cog install RSCBot prefixManager
<p>load prefixManager
```

## Imporant Note

With improvements made to the `teamManager` cog, many of these commands are unnecessary to use. With the `teamManager` cog, franchise management is simplified with commands such as `<p>addFranchise` and `<p>removeFranchise`. However, this cog **must** still be installed and loaded.

## Usage

The following commands can be used to manage server prefixes:

- `<p>addPrefix <gm_name> <prefix>`
  - This command can be used to add one GM/prefix association
  - Note: A franchise role must be manually added in the correct format for a GM and his franchise to be recognized.
  - Example: `<p>addPrefix Adammast OCE`
- `<p>addPrefixes [prefixes_to_add]`
  - This can be used to add mutliple prefixes at a time.
  - `[prefixes_to_add]` must be in the following format: "['<gm_name>','<prefix>']"
  - Note: For each prefix added, a franchise role must be manually added in the correct format for a GM and his franchise to be recognized.
  - Examples:
    - `<p>addPrefixes "['Adammast','OCE']"`
    - `<p>addPrefixes [p]addPrefixes "['Adammast','OCE']" "['Shamu','STM']"`
  - `<p>getPrefixes` (aliases: `<p>prefixes`, `<p>listPrefixes`)
    - displays all prefix assocations
  - `<p>removePrefix <gm_name>`
    - Removes the prefix association with the given GM.
  - `<p>clearPrefixes`
    - removes all GM/prefix associations
  - `<p>lookupPrefix <gm_name>`
    - displays the prefix association for the provided GM if one is found.
  - `<p>removeNicknames [userList]`
    - Removes nicknames for each user passed in the userList. The `teamManager` cog uses prefixes and nicknames to reflect which franchise discord members are associated with.
    - Example: `<p>removeNicknames Adammast nullidea Snipe`


## What if a GM changes?

If a GM wishes to step down, or leaves the server, the prefix and the franchise role name must be updated.
- The discord role name may be updated in server settings.
- The commands `<p>removePrefix` and `<p>addPrefix` may be used to update the prefix association to the newly appointed GM.
