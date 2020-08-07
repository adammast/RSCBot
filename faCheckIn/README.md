# RSCBot: faCheckIn

The `faCheckIn` cog is primarily responsible for helping manage Free Agent substitutions. This cog allows for Free Agents to check in or check out to indicate availability for substitution. Teams who need a substitute may check availability for free agents at a given tier.

## Installation

The `faCheckIn` cog depends on the `match` and `teamManager` cogs. Install `match` and `teamManager` as well as other dependencies before installing `faCheckIn`.

```
<p>cog install RSCBot faCheckIn
<p>load faCheckIn
```

## Usage

- `<p>checkIn` (alias: `<p>ci`)
  - Sets the invoker as being available for substitution
- `<p>checkOut` (alias: `<p>co`)
  - Sets the invoker as being unavailable for substitution
- `<p>checkAvailability <tier_name> [match_day]` (alias: `<p>ca`)
  - Checks availability for a tier on a particular match day. If `match_day` is not provided, it will default to the current match day.
- `<p>clearAvailaibility [tier] [match_day]`
  - Removes availaibility for a given tier/match day.
- `<p>clearAllAvailability`
  - Clears the full log of match availability.
  