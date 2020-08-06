# RSCBot: transactions

The `transactions` cog is primarily responsible for managing team rosters. This cog can manage transactions such as drafts, signs, cuts, substitutions, and simple trades. Complex trades may be managed manually, and announced with the `genericAnnouncement` command.

## Installation

The `transactions` cog depends on the `prefixManager` and `teamManager` cogs. Install `prefixManager` and `teamManager` before installing `transactions`.

```
<p>cog install RSCBot transactions
<p>load transactions
```

## Usage

A transaction channel must be set before any transactions may occur. This channel is used to annouce/log all transactions in the server.

Active players will have roles and nicknames that reflect their association to a franchise, tier and/or free agency.

Franchise players will have the franchise prefix in their nicknames and the associated roles. Free Agents will have a "FA" prefix in their name and free agency roles assigned ("Free Agent", "<tier>FA").

- `<p>setTransactionChannel <trans_channel>`
  - sets the dedicated channel for announcing league transactions.
- `<p>getTransactionChannel`
  - Returns the transaction channel if one has been set.
- `<p>unsetTransactionChannel`
  - Unsets transaction channel and disables transactions until one has been set again.
- `<p>genericAnnouncement <message>`
  - Posts the message to the transaction log channel
- `<p>draft <user> <team_name> [round] [pick]`
  - Drafts a player to the provided team. Assignes the tier and franchise role to the player, and announces the selection in the transaction channel.
- `<p>sign <user> <team_name>`
  - Signs a player to the provided team. Assignes the tier and franchise role to the player, and announces the selection in the transaction channel.
- `<p>cut <user> <team_name> [tier_fa_role]`
  - Removes a player from their team, and removes their franchise role, and registers as a Free Agent.
  - If `tier_fa_role` is provided, it will assign the tier and tier FA role to the user.
  - (Pending) Note: No role changes will be made to GMs
- `<p>trade <user> <new_team_name> <user_2> <new_team_2>`
  - Swaps the teams of the two players and announces the trade in the assigned transaction channel
- `<p>sub <user> <team_name>`
  - Used to temporarily add a substitute player to the team provided. Substitutes can be Free Agents, or players who already belong to the same franchise.
  - This command is also used to end substitution periods.
- `<p>promote <user> <team_name>`
  - Promotes a user to the provided team within the same franchise. Updates tier role assigned to the user.
