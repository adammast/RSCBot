# RSCBot: teamManager

The `teamManager` cog is primarily responsible for managing franchises, thier teams, and tiers.

## Installation

The `teamManager` cog depends on the `prefixManager` cog. Install `prefixManager` before installing `teamManager`.

```
<p>cog install RSCBot teamManager
<p>load teamManager
```

## Usage

Franchises and tiers must be created before any teams may be added. The `transactions` cog is responsible for adding and removing players from teams.

- `<p>addFranchise <gm> <franchise_prefix> <franchise name>`
  - Creates a new franchise in the discord server:
    - Adds a prefix association between `gm` and `franchise_prefix`
    - Adds a discord role for the franchise in the correct format: [<franchise_name> (<gm_name>)](https://media.discordapp.net/attachments/679698891129880580/707975741505273938/Capture.PNG)
    - Updates GM details
      - Adds GM role
      - Updates Nickname to include prefix (`<franchise_prefix> | <GM name>`)
    - Example:
      - `<p>addFranchise Adammast OCE The Ocean`
        - GM: 'Adammast'
        - Prefix: 'OCE'
        - Franchise Name: 'The Ocean'
        - GM nickname: 'OCE | Adammast'
- `<p>removeFranchise <gm>`
  - removes the prefix and discord role associated with the franchise
  - removes the GM's role and nickname prefix
  - removes "General Manager" role from GM.
- `<p>franchises` (aliases: `getFranchises`, `<p>listFranchises`)
  - Lists all franchises found in the server.
- `<p>teams <franchise_tier_prefix>`
  - Displays all teams for a given franchise or tier
  - Examples:
    - `<p>teams The Ocean`
    - `<p>teams OCE`
    - `<p>teams Challenger`
- `<p>roster <team_name>`
  - Displays the GM and all members of the team provided.
- `<p>captains <franchise_tier_prefix>`
  - Displays all captains for a franchise or tier
  - Examples:
    - `<p>captains The Ocean`
    - `<p>captains Adammast`
    - `<p>captains OCE`
    - `<p>captains Challenger`
- `<p>addTier <tier_name>`
  - Adds a tier to the discord guild
    - Saves tier to database
    - Creates `<tier>` and `<tier>FA` roles
- `<p>removeTier <tier_name>`
  - Removes tier from the database, and its associated roles
- `<p>listTiers` (aliases: `<p>tiers`, `<p>getTiers`)
  - Displays all tiers registerd in the discord server
- `<p>addTeam <team_name> <gm_name> <tier>`
  - Adds a team to a GM's franchise for the provided tier.
  - Adds the tier role to the GM
- `<p>addTeams [teams_to_add]`
  - Adds a list of teams to the server.
  - `teams_to_add` must be in the following format: "['<team_name>','<gm_name>','<tier>']"
  - Examples:
    - `<p>addTeams "['Derechos','Shamu','Challenger']"`
    - `<p>addTeams "['Derechos','Shamu','Challenger']" "['Barbarians','Snipe','Challenger']"`
- `<p>removeTeam <team_name>`
  - Removes the team from its franchise
  - Removes the team's tier role from the GM
- `<p>clearTeams`
  - Removes all teams from the file system. Team roles will be cleared as well
- `<p>teamRoles`
  - Prints out the franchise and tier role that corresponds with the given team
- `<p>freeAgents <tier> [filter]` (aliases: `<p>fa`, `<p>fas`)
  - Displays all free agents for the given tier
  - Filter may be applied to display only unrestricted (signable) FAs or restricted (permanent) FAs.


## What if a GM changes?

If a GM wishes to step down, or leaves the server, the prefix and the franchise role name must be updated.
- Coming Soon: `<p>transferFranchise`
- Until this addition is made, franchises may be recovered or transferred with commands from the `prefixManager` cog. (See [prefixManager docs](https://github.com/adammast/RSCBot/tree/master/prefixManager))
