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
- `<p>checkOut` (alias: `<p>co`)
- `<p>checkAvailability <tier_name> [match_day]` (alias: `<p>ca`)
- `<p>clearAvailaibility [tier] [match_day]`
- `<p>clearAllAvailability`