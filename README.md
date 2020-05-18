# RSCBot

RSCBot is a collection of cogs written in Python that can be installed and used with the [Red Discord Bot](https://docs.discord.red/en/stable/index.html). These cogs are primarily written for use within [RSC (Rocket Soccar Confederation)](https://www.rocketsoccarconfederation.com/), a 3v3 Rocket League Amateur League that runs through [Discord](https://discord.gg/Q6RkvYm).

## Installation

Follow the Red Discord Bot installation guide for [Windows](https://docs.discord.red/en/stable/install_windows.html) or [Linux/Mac](https://docs.discord.red/en/stable/install_linux_mac.html). You'll need to also [create a Discord bot account](https://discordpy.readthedocs.io/en/latest/discord.html) to get a token for use during the bot setup. After you have the bot setup, running, and invited to one of your Discord servers, you can begin installing and loading the cogs to the bot using the following commands in Discord (where `<p>` represents the prefix you selected your bot to use):

```
<p>load downloader
<p>repo add RSCBot https://github.com/adammast/RSCBot [branch]
<p>cog install RSCBot <cog_name>
<p>load <cog_name>
```

Certain cogs depend on another cog being loaded first in order to work correctly. You can see a visualization of the cog dependencies [here](https://docs.google.com/drawings/d/1Ys3Ne_66uTECXY47WTLPr3LlWi_XL8rUGf2S90jY7Nk/edit?usp=sharing). Any cog that isn't shown in that chart is a stand-alone cog that can be loaded whenever and will work on its own.

## Usage

Many of the RSC league specific cogs rely on roles being set up in the Discord server a certain way or data, such as team names and prefixes, to be added to the bot before they can be used. In this section I'll attempt to explain all the steps required in setting up the league specifics cogs correctly.

#### Commands

For any command, you can see documentation explaining how to use the command with the format: `<p>help <command name>`

#### Franchises/Prefixes

As can be seen in the [cog dependencies doc](https://docs.google.com/drawings/d/1Ys3Ne_66uTECXY47WTLPr3LlWi_XL8rUGf2S90jY7Nk/edit?usp=sharing), the prefixManager cog should be the first cog loaded from the league specific cogs. For RSC, a prefix should be added for each franchise within the league. To add a prefix you first need to set up a franchise role with the following name format: [<franchise_name> (<GM_name>)](https://media.discordapp.net/attachments/679698891129880580/707975741505273938/Capture.PNG). After that the `<p>addPrefix` command can be used to add prefixes one at a time, or the `<p>addPrefixes` command can be used to add them in bulk. Alternatively, the command `<p>addFranchise` to complete all of these steps for adding a single team simultaneously.

#### Tiers

Tiers are added through the teamManager cog using the `<p>addTier` command. The bot will accept any name for the tier. This will create a role for the tier, which along with the franchise roles, will be used to help determine what team a player is currently on. For each tier added, a corresponding free agent role will also be generated. For example, for a tier named `Premier` the role `Premier` and a free agent role named `PremierFA` will be generated.

#### Teams

For RSC, each team will need to have a team name, a corresponding GM (General Manager), and a tier that the team plays in (which are generated from previous commands). Each tier should already be loaded into the bot according to the Tiers subsection above. Teams need to be added to the bot in order to use commands such as `<p>match`, `<p>roster`, or any of the transaction commands. Most of the commands involving teams are in the teamManager cog. To add a team to the bot the `<p>addTeam` command can be used to add them one at a time, or the `<p>addTeams` command can be used to add them in bulk. When a team is added to a franchise, the GM is given the tier role to reflect the addition of the team at that tier.

#### Matches

The match cog is used for easy propagation of match information within RSC. Both teams involved in the match need to be added to the bot according to the Teams subsection above. Matches need to be added and the match day set in order to use any of the faCheckIn cog commands. To add a match to the bot the `<p>addMatch` command can be used to add them one at a time, or the `<p>addMatches` command can be used to add them in bulk. You can use `<p>help addMatch` and `<p>help addMatches` in Discord to see documentation explaining how to use each command.

#### Free Agent Role

Along with the tier specific free agent roles mentioned in the Tiers subsection above, you'll also want a general free agent role named `Free Agent`. This role is used in some of the transaction commands to determine if a player is a free agent or not.

#### Draft Eligible Role

For players who are eligible for the league's upcoming draft there should be a role named `Draft Eligible`. This role is used in some of the transaction commands and also used in the makeDE command from the bulkRoleManager cog.

## Contributing

Pull requests are welcome! Feel free to contact me in Discord (adammast#0190) for any questions or discussions on larger issues.

## License

[MIT](https://choosealicense.com/licenses/mit/)
