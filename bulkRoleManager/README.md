# RSCBot: bulkRoleManager

The `bulkRoleManager` cog is primarily responsible for monitoring and managing member roles in large quantities. This largely pertains to setting tier, draft eligible, or free agent roles to mutliple players at a time.

## Installation

The `bulkRoleManager` cog depends on the `teamManager` cog. Install `teamManager` as well as its dependencies before installing `bulkRoleManager`.

```
<p>cog install RSCBot bulkRoleManager
<p>load bulkRoleManager
```

## Usage

- `<p>getAllWithRole <role> [getNickname]`
  - Returns every member in the server with the provided role
  - if `getNickname` is True, the command will also provide the nicknames for each member found.
- `<p>removeRoleFromAll <role>`
  - Removes the role from everyone in the server who has it.
- `<p>addRole <role> [userList]`
  - Adds the provided role to each member that can be found in the userList.
- `<p>removeRole <role> [userList]`
  - Removes the role from every member that can be found from the userList.
- `<p>getId [userList]`
  - Gets the id for any user that can be found from the userList
- `<p>getIdsWithRole <role> [spreadsheet]`
  - Gets the id for any user that has the given role.
  - If spreadsheet is set to True, then a file will be saved with the command results.
- `<p>giveRoleToAllWithRole <currentRole> <roleToGive>`
  - Assigns the role, `roleToGive` to every member in the server who has the role `currentRole`.
  - Example: This could be used to give every `<tier>FA` member the `<tier>` role.
    - `<p>giveRoleToAllWithRole MajorFA Major`
- `<p>makeDE [userList]`
  - Adds the 'Draft Eligible' and 'League' roles, removes the 'Spectator' role, and adds the DE prefix to every member that can be found from the userList.
  - This also sends each newly Draft Eligible player a direct message if one has been set.
- `<p>getDEMessage`
  - Gets the message that is sent to newly declared draft eligible players. (Default: None)
- `<p>setDEMessage <message>`
  - Sets the message that is sent to newly declared draft eligible players.

### Coming soon:

- `<p>retire [userList]`
  - Removes all league roles (franchise, tier, free agent, league) and assigns the "Former Player" role. This additionally will clear the user's nickname prefix.
  