from .config import config
import requests
import tempfile
import os
import json
import discord
import asyncio

from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions
from datetime import datetime, timezone


defaults = {
    "AuthToken": config.auth_token,
    "TopLevelGroup": config.top_level_group,
    "TierRank": config.tier_rank,
    "ReplayDumpChannel": None
}
global_defaults = {"AccountRegister": {}}
verify_timeout = 30

class BCManager(commands.Cog):
    """Manages aspects of Ballchasing Integrations with RSC"""

    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567893, force_registration=True)
        self.config.register_guild(**defaults)
        self.config.register_global(**global_defaults)
        self.team_manager_cog = bot.get_cog("TeamManager")
        self.match_cog = bot.get_cog("Match")
    
    @commands.command(aliases=['bcr', 'bcpull'])
    @commands.guild_only()
    async def bcreport(self, ctx, team_name=None, match_day=None):
        """Finds match games from recent public uploads, and adds them to the correct Ballchasing subgroup
        """

        # Get match information
        member = ctx.message.author
        match = await self.get_match(ctx, member, team_name, match_day)

        if not match:
            await ctx.send(":x: No match found.")
            return False

        # Get team/tier information
        match_day = match['matchDay']
        franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, match['home'])
        emoji_url = ctx.guild.icon_url

        embed = discord.Embed(
            title="Match Day {}: {} vs {}".format(match_day, match['home'], match['away']),
            description="Searching https://ballchasing.com for publicly uploaded replays of this match...",
            color=tier_role.color
        )
        if emoji_url:
            embed.set_thumbnail(url=emoji_url)
        bc_status_msg = await ctx.send(embed=embed)
        

        # Find replays from ballchasing
        replays_found = await self._find_match_replays(ctx, member, match)

        ## Not found:
        if not replays_found:
            embed.description = ":x: No matching replays found on ballchasing."
            await bc_status_msg.edit(embed=embed)
            return False
        
        ## Found:
        replay_ids, summary, winner = replays_found
        
        if winner:
            franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, winner)
            emoji = await self.team_manager_cog._get_franchise_emoji(ctx, franchise_role)
            emoji_url = emoji.url
        

        # Prepare embed edits for score confirmation
        prompt_embed = discord.Embed.from_dict(embed.to_dict())
        prompt_embed.description = "Match summary:\n{}".format(summary)
        prompt_embed.set_thumbnail(url=emoji_url)
        prompt_embed.description += "\n\nPlease react to confirm the score summary for this match."

        success_embed = discord.Embed.from_dict(prompt_embed.to_dict())
        success_embed.description = "Match summary:\n{}".format(summary)
        success_embed.description += "\n\n:signal_strength: Results confirmed. Creating a ballchasing replay group. This may take a few seconds..." # "\U0001F4F6"

        reject_embed = discord.Embed.from_dict(prompt_embed.to_dict())
        reject_embed.description = "Match summary:\n{}".format(summary)
        reject_embed.description += "\n\n:x: Ballchasing upload has been cancelled."
        
        if not await self._embed_react_prompt(ctx, prompt_embed, existing_message=bc_status_msg, success_embed=success_embed, reject_embed=reject_embed):
            return False
        
        # Find or create ballchasing subgroup
        match_subgroup_id = await self._get_replay_destination(ctx, match)

        # Download and upload replays
        tmp_replay_files = await self._download_replays(ctx, replay_ids)
        uploaded_ids = await self._upload_replays(ctx, match_subgroup_id, tmp_replay_files)
        # await ctx.send("replays in subgroup: {}".format(", ".join(uploaded_ids)))
        
        renamed = await self._rename_replays(ctx, uploaded_ids)

        embed.description = "Match summary:\n{}\n\nView the ballchasing group: https://ballchasing.com/group/{}\n\n:white_check_mark: Done".format(summary, match_subgroup_id)
        embed.set_thumbnail(url=emoji_url)
        await bc_status_msg.edit(embed=embed)
        
    @commands.command(aliases=['setAuthKey'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def setAuthToken(self, ctx, auth_token):
        """Sets the Auth Key for Ballchasing API requests.
        Note: Auth Token must be generated from the Ballchasing group owner
        """
        token_set = await self._save_auth_token(ctx, auth_token)
        if token_set:
            await ctx.send("Done.")
        else:
            await ctx.send(":x: Error setting auth token.")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def setTierRank(self, ctx, tier, rank):
        """Declares a ranking of tiers so that they are sorted in accordance with skill distribution
        """
        tiers = await self.team_manager_cog.tiers(ctx)
        tier_found = False
        for t in tiers:
            if t.lower() == tier.lower():
                tier_found = True
                break
        
        old_rank = None
        tier_ranks = await self._get_tier_ranks(ctx)
        if tier in tier_ranks:
            old_rank = tier_ranks['tier']
        
        if old_rank != rank:
            await ctx.send("The **{}** rank was changed from {} to {}".format(tier=tier.Title(), old_rank=old_rank, new_rank=rank))
        else:
            await ctx.send("Done")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def setTopLevelGroup(self, ctx, top_level_group):
        """Sets the Top Level Ballchasing Replay group for saving match replays.
        Note: Auth Token must be generated from the Ballchasing group owner
        """
        group_set = await self._save_top_level_group(ctx, top_level_group)
        if(group_set):
            await ctx.send("Done.")
        else:
            await ctx.send(":x: Error setting top level group.")
    
    @commands.command(aliases=['bcGroup', 'ballchasingGroup', 'bcg'])
    @commands.guild_only()
    async def bcgroup(self, ctx):
        """Links to the top level ballchasing group for the current season."""
        group_code = await self._get_top_level_group(ctx)
        url = "https://ballchasing.com/group/{}".format(group_code)
        if group_code:
            await ctx.send("See all season replays in the top level ballchasing group: {}".format())
        else:
            await ctx.send(":x: A ballchasing group has not been set for this season yet.")

    @commands.command(aliases=['accountRegister', 'addAccount'])
    @commands.guild_only()
    async def registerAccount(self, ctx, platform, identifier):
        """Allows user to register account for ballchasing requests. This may be found by searching your appearances on ballchasing.com
        **Note:** Only **steam** accounts can be used to find match replays.
        Examples:
            [p]registerAccount steam 76561199096013422
            [p]registerAccount xbox e4b17b0000000900
            [p]registerAccount ps4 touchetupac2
            [p]registerAccount epic 76edd61bd58841028a8ee27373ae307a
        """

        # Check platform
        if platform.lower() not in ['steam', 'xbox', 'ps4', 'ps5', 'epic']:
            await ctx.send(":x: \"{}\" is an invalid platform".format(platform))
            return False

        # Validate account -- check for public ballchasing appearances
        valid_account = await self._validate_account(ctx, platform, identifier)
        if valid_account:
            username, appearances = valid_account
        else:
            await ctx.send(":x: No ballchasing replays found for user: {identifier} ({platform}) ".format(identifier=identifier, platform=platform))
            return False

        # React to confirm account registration
        if str(appearances) == "10000":
            appearances = "{}+".format(appearances)
        prompt = "**{username}** ({platform}) appears in **{count}** ballchasing replays.".format(username=username, platform=platform, count=appearances)
        prompt += "\n\nWould you like to register this account?"
        nvm_message = "Registration cancelled."
        if not await self._react_prompt(ctx, prompt, nvm_message):
            return False
        
        account_register = await self._get_account_register()
        pid = str(ctx.message.author.id)
        if pid in account_register:
            account_register[pid].append([platform, identifier])
        else:
            account_register[pid] = [[platform, identifier]]

        # Register account
        await self._save_account_register(account_register)
        await ctx.send("Done")
    
    @commands.command(aliases=['rmaccount', 'removeAccount'])
    @commands.guild_only()
    async def unregisterAccount(self, ctx, platform, identifier=None):
        """Removes one or more registered accounts."""
        remove_accs = []
        account_register = await self._get_account_register()
        member = ctx.message.author
        if str(member.id) in account_register:
            for account in account_register[str(member.id)]:
                if account[0] == platform:
                    if not identifier or account[1] == identifier:
                        remove_accs.append(account)
        
        if not remove_accs:
            await ctx.send(":x: No matching account has been found.")
            return False
        
        prompt = "React to confirm removal of the following account(s):\n - " + "\n - ".join("{}: {}".format(acc[0], acc[1]) for acc in remove_accs)
        if not await self._react_prompt(ctx, prompt, "No accounts have been removed."):
            return False
        
        count = 0
        for acc in remove_accs:
            account_register[str(member.id)].remove(acc)
            count += 1
        
        await self._save_account_register(account_register)
        await ctx.send(":white_check_mark: Removed **{}** account(s).".format(count))

    @commands.command(aliases=['rmaccounts', 'clearaccounts', 'clearAccounts'])
    @commands.guild_only()
    async def unregisterAccounts(self, ctx):
        """Unlinks registered account for ballchasing requests."""
        account_register = await self._get_account_register(ctx.guild)
        discord_id = str(ctx.message.author.id)
        if discord_id in account_register:
            count = len(account_register[discord_id])
            accounts = await self._get_all_accounts(ctx, ctx.message.author)
            prompt = "React to confirm removal of the following accounts ({}):\n - ".format(len(accounts)) + "\n - ".join("{}: {}".format(acc[0], acc[1]) for acc in accounts)
            if not await self._react_prompt(ctx, prompt, "No accounts have been removed."):
                return False
            
            del account_register[discord_id]
            await ctx.send(":white_check_mark: Removed **{}** account(s).".format(count))
        else:
            await ctx.send("No account found.")

    @commands.command(aliases=['accs', 'myAccounts', 'registeredAccounts'])
    @commands.guild_only()
    async def accounts(self, ctx):
        """View all accounts that have been registered to with your discord account in this guild."""
        member = ctx.message.author
        accounts = await self._get_member_accounts(member)
        if not accounts:
            await ctx.send("{}, you have not registered any accounts.".format(member.mention))
            return

        show_accounts = "{}, you have registered the following accounts:\n - ".format(member.mention) + "\n - ".join("{}: {}".format(acc[0], acc[1]) for acc in accounts)
        await ctx.send(show_accounts)

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def massAddAccounts(self, ctx):
        """Adds accounts in bulk -- This is not supported yet"""
        pass
    
    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearAccountData(self, ctx):
        """Clears all account data -- This is not supported yet"""
        pass


    # @commands.Cog.listener("on_message")
    # async def on_message(self, message):
    #     member = message.author


    async def _bc_get_request(self, ctx, endpoint, params=[], auth_token=None):
        if not auth_token:
            auth_token = await self._get_auth_token(ctx.guild)
        
        url = 'https://ballchasing.com/api'
        url += endpoint
        params = '&'.join(params)
        if params:
            url += "?{}".format(params)
        
        return requests.get(url, headers={'Authorization': auth_token})

    async def _bc_post_request(self, ctx, endpoint, params=[], auth_token=None, json=None, data=None, files=None):
        if not auth_token:
            auth_token = await self._get_auth_token(ctx.guild)
        
        url = 'https://ballchasing.com/api'
        url += endpoint
        params = '&'.join(params)
        if params:
            url += "?{}".format(params)
        
        return requests.post(url, headers={'Authorization': auth_token}, json=json, data=data, files=files)

    async def _bc_patch_request(self, ctx, endpoint, params=[], auth_token=None, json=None, data=None):
        if not auth_token:
            auth_token = await self._get_auth_token(ctx.guild)

        url = 'https://ballchasing.com/api'
        url += endpoint
        params = '&'.join(params)
        if params:
            url += "?{}".format(params)
        
        return requests.patch(url, headers={'Authorization': auth_token}, json=json, data=data)

    async def _react_prompt(self, ctx, prompt, if_not_msg=None, embed:discord.Embed=None):
        user = ctx.message.author
        if embed:
            embed.description = prompt
            react_msg = await ctx.send(embed=embed)
        else:
            react_msg = await ctx.send(prompt)
        start_adding_reactions(react_msg, ReactionPredicate.YES_OR_NO_EMOJIS)
        try:
            pred = ReactionPredicate.yes_or_no(react_msg, user)
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=verify_timeout)
            if pred.result:
                return True
            if if_not_msg:
                await ctx.send(if_not_msg)
            return False
        except asyncio.TimeoutError:
            await ctx.send("Sorry {}, you didn't react quick enough. Please try again.".format(user.mention))
            return False

    async def _embed_react_prompt(self, ctx, embed, existing_message=None, success_embed=None, reject_embed=None, clear_after_confirm=True):
        user = ctx.message.author
        if existing_message:
            react_msg = existing_message
            await react_msg.edit(embed=embed)
        else:
            react_msg = await ctx.send(embed=embed)
        
        start_adding_reactions(react_msg, ReactionPredicate.YES_OR_NO_EMOJIS)
        try:
            pred = ReactionPredicate.yes_or_no(react_msg, user)
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=verify_timeout)
            if pred.result:
                await react_msg.edit(embed=success_embed)
                if clear_after_confirm:
                    await react_msg.clear_reactions()
                return True
            if reject_embed:
                await react_msg.edit(embed=reject_embed)
            return False
        except asyncio.TimeoutError:
            await react_msg.edit(embed=reject_embed)
            await ctx.send("Sorry {}, you didn't react quick enough. Please try again.".format(user.mention))
            return False

    async def _get_steam_ids(self, guild, discord_id):
        discord_id = str(discord_id)
        steam_accounts = []
        account_register = await self._get_account_register()
        if discord_id in account_register:
            for account in account_register[discord_id]:
                if account[0] == 'steam':
                    steam_accounts.append(account[1])
        return steam_accounts
    
    async def _get_member_accounts(self, member):
        accs = []
        account_register = await self._get_account_register()
        discord_id = str(member.id)
        if discord_id in account_register:
            for account in account_register[discord_id]:
                accs.append(account)
        return accs
    
    async def _validate_account(self, ctx, platform, identifier):
        auth_token = config.auth_token
        endpoint = '/replays'
        params = [
            'player-id={platform}:{identifier}'.format(platform=platform, identifier=identifier),
            'count=1'
        ]
        r = await self._bc_get_request(ctx, endpoint, params)
        data = r.json()

        appearances = 0
        username = None
        if data['list']:
            for team_color in ['blue', 'orange']:
                for player in data['list'][0][team_color]['players']:
                    if player['id']['platform'] == platform and player['id']['id'] == identifier:
                        username = player['name']
                        appearances = data['count']
                        break
        if username:
            return username, appearances
        return False

    def get_replay_teams(self, replay):
        try:
            blue_name = replay['blue']['name'].title()
        except:
            blue_name = "Blue"
        try:
            orange_name = replay['orange']['name'].title()
        except:
            orange_name = "Orange"

        blue_players = []
        for player in replay['blue']['players']:
            blue_players.append(player['name'])
        
        orange_players = []
        for player in replay['orange']['players']:
            orange_players.append(player['name'])
        
        teams = {
            'blue': {
                'name': blue_name,
                'players': blue_players
            },
            'orange': {
                'name': orange_name,
                'players': orange_players
            }
        }
        return teams

    async def _get_steam_id_from_token(self, ctx, auth_token=None):
        if not auth_token:
            auth_token = await self._get_auth_token(ctx.guild)
        r = await self._bc_get_request(ctx, "")
        if r.status_code == 200:
            return r.json()['steam_id']
        return None

    def get_player_id(discord_id):
        arr = config.account_register[discord_id]
        player_id = "{}:{}".format(arr[0], arr[1])
        return player_id

    async def _get_uploader_id(self, ctx, discord_id):
        account_register = await self._get_account_register()
        if ctx.member.id in account_register:
            if account_register[discord_id][0] != 'steam':
                return account_register[discord_id][1]
        return None

    def is_full_replay(self, replay_data):
        if replay_data['duration'] < 300:
            return False
        
        blue_goals = replay_data['blue']['goals'] if 'goals' in replay_data['blue'] else 0
        orange_goals = replay_data['orange']['goals'] if 'goals' in replay_data['orange'] else 0
        if blue_goals == orange_goals:
            return False
        for team in ['blue', 'orange']:
            for player in replay_data[team]['players']:
                if player['start_time'] == 0:
                    return True
        return False

    def is_match_replay(self, match, replay_data):
        match_day = match['matchDay']   # match cog
        home_team = match['home']       # match cog
        away_team = match['away']       # match cog

        if not self.is_full_replay(replay_data):
            return False

        replay_teams = self.get_replay_teams(replay_data)

        home_team_found = replay_teams['blue']['name'].lower() in home_team.lower() or replay_teams['orange']['name'].lower() in home_team.lower()
        away_team_found = replay_teams['blue']['name'].lower() in away_team.lower() or replay_teams['orange']['name'].lower() in away_team.lower()

        return home_team_found and away_team_found

    async def get_match(self, ctx, member, team=None, match_day=None):
        if not match_day:
            match_day = await self.match_cog._match_day(ctx)
        if not team:
            team = (await self.team_manager_cog.teams_for_user(ctx, member))[0]
        
        match = await self.match_cog.get_match_from_day_team(ctx, match_day, team)
        return match

    async def _get_replay_destination(self, ctx, match, top_level_group=None, group_owner_discord_id=None):
        
        auth_token = await self._get_auth_token(ctx.guild)

        # needs both to override default -- TODO: Remove non-match params (derive logically)
        if not group_owner_discord_id or not top_level_group:
            bc_group_owner = await self._get_steam_id_from_token(ctx, auth_token)
            top_level_group = await self._get_top_level_group(ctx)
        else:
            bc_group_owner = await self._get_uploader_id(ctx, group_owner_discord_id)  # config.group_owner_discord_id

        # RSC/<top level group>/<tier num><tier>/Match Day <match day>/<Home> vs <Away>
        tier = (await self.team_manager_cog._roles_for_team(ctx, match['home']))[1].name  # Get tier role's name
        tier_group = await self._get_tier_subgroup_name(ctx, tier)
        ordered_subgroups = [
            tier_group,
            "Match Day {}".format(str(match['matchDay']).zfill(2)),
            "{home} vs {away}".format(home=match['home'].title(), away=match['away'].title())
        ]

        endpoint = '/groups'
        
        params = [
            # 'player-id={}'.format(bcc_acc_rsc),
            'creator={}'.format(bc_group_owner),
            'group={}'.format(top_level_group)
        ]

        r = await self._bc_get_request(ctx, endpoint, params, auth_token)
        data = r.json()

        # Dynamically create sub-group
        current_subgroup_id = top_level_group
        next_subgroup_id = None
        for next_group_name in ordered_subgroups:
            if next_subgroup_id:
                current_subgroup_id = next_subgroup_id
            next_subgroup_id = None 

            # Check if next subgroup exists
            if 'list' in data:
                for data_subgroup in data['list']:
                    if data_subgroup['name'] == next_group_name:
                        next_subgroup_id = data_subgroup['id']
                        break
            
            # Prepare & Execute  Next request:
            # ## Next subgroup found: request its contents
            if next_subgroup_id:
                params = [
                    'creator={}'.format(bc_group_owner),
                    'group={}'.format(next_subgroup_id)
                ]

                r = await self._bc_get_request(ctx, endpoint, params, auth_token)
                data = r.json()

            # ## Creating next sub-group
            else:
                payload = {
                    'name': next_group_name,
                    'parent': current_subgroup_id,
                    'player_identification': config.player_identification,
                    'team_identification': config.team_identification
                }
                r = await self._bc_post_request(ctx, endpoint, auth_token=auth_token, json=payload)
                data = r.json()
                
                try:
                    next_subgroup_id = data['id']
                except:
                    await ctx.send(":x: Error creating Ballchasing group: {}".format(next_group_name))
                    return False
            
        return next_subgroup_id

    async def _find_match_replays(self, ctx, member, match):
        # search for appearances in private matches
        endpoint = "/replays"
        sort = 'replay-date' # 'created
        sort_dir = 'desc' # 'asc'
        count = config.search_count

        # RFC3339 Date/Time format
        now = datetime.now(timezone.utc).astimezone().isoformat()
        adj_char = '+' if '+' in str(now) else '-'
        zone_adj = "{}{}".format(adj_char, str(now).split(adj_char)[-1])

        date_string = match['matchDate']
        match_date = datetime.strptime(date_string, '%B %d, %Y').strftime('%Y-%m-%d')
        start_match_date_rfc3339 = "{}T00:00:00{}".format(match_date, zone_adj)
        end_match_date_rfc3339 = "{}T23:59:59{}".format(match_date, zone_adj)

        params = [
            # 'uploader={}'.format(uploader),
            'playlist=private',
            # 'replay-date-after={}'.format(start_match_date_rfc3339),  # Filters by matches played on this day
            # 'replay-date-before={}'.format(end_match_date_rfc3339),
            'count={}'.format(count),
            'sort-by={}'.format(sort),
            'sort-dir={}'.format(sort_dir)
        ]

        auth_token = await self._get_auth_token(ctx.guild)
        all_players = await self._get_all_match_players(ctx, match)
        
        # Search invoker's replay uploads first
        if member in all_players:
            all_players.remove(member)
            member.insert(0 member)
        
        # Search all players in game for replays until match is found
        for player in all_players:
            for steam_id in await self._get_steam_ids(ctx.guild, player.id):
                uploaded_by_param='uploader={}'.format(steam_id)
                params.append(uploaded_by_param)

                r = await self._bc_get_request(ctx, endpoint, params=params, auth_token=auth_token)
                data = r.json()
                params.remove(uploaded_by_param)

                # checks for correct replays
                home_wins = 0
                away_wins = 0
                replay_ids = []
                for replay in data['list']:
                    if self.is_match_replay(match, replay):
                        replay_ids.append(replay['id'])
                        if replay['blue']['name'].lower() in match['home'].lower():
                            home = 'blue'
                            away = 'orange'
                        else:
                            home = 'orange'
                            away = 'blue'
                        
                        home_goals = replay[home]['goals'] if 'goals' in replay[home] else 0
                        away_goals = replay[away]['goals'] if 'goals' in replay[away] else 0
                        if home_goals > away_goals:
                            home_wins += 1
                        else:
                            away_wins += 1

                series_summary = "**{home_team}** {home_wins} - {away_wins} **{away_team}**".format(
                    home_team = match['home'],
                    home_wins = home_wins,
                    away_wins = away_wins,
                    away_team = match['away']
                )
                winner = None
                if home_wins > away_wins:
                    winner = match['home']
                elif home_wins < away_wins:
                    winner = match['away']

                if replay_ids:
                    return replay_ids, series_summary, winner
        return None
    
    async def _download_replays(self, ctx, replay_ids):
        auth_token = await self._get_auth_token(ctx.guild)
        tmp_replay_files = []
        this_game = 1
        for replay_id in replay_ids[::-1]:
            endpoint = "/replays/{}/file".format(replay_id)
            r = await self._bc_get_request(ctx, endpoint, auth_token=auth_token)
            
            # replay_filename = "Game {}.replay".format(this_game)
            replay_filename = "{}.replay".format(replay_id)
            
            tf = tempfile.NamedTemporaryFile()
            tf.name += ".replay"
            tf.write(r.content)
            tmp_replay_files.append(tf)
            this_game += 1

        return tmp_replay_files

    async def _upload_replays(self, ctx, subgroup_id, files_to_upload):
        endpoint = "/v2/upload"
        params = [
            'visibility={}'.format(config.visibility),
            'group={}'.format(subgroup_id)
        ]
        auth_token = await self._get_auth_token(ctx.guild)

        replay_ids_in_group = []
        for replay_file in files_to_upload:
            replay_file.seek(0)
            files = {'file': replay_file}

            r = await self._bc_post_request(ctx, endpoint, params, auth_token=auth_token, files=files)
        
            status_code = r.status_code
            data = r.json()

            try:
                if status_code == 201:
                    replay_ids_in_group.append(data['id'])
                elif status_code == 409:
                    payload = {
                        'group': subgroup_id
                    }
                    r = await self._bc_patch_request(ctx, '/replays/{}'.format(data['id']), auth_token=auth_token, json=payload)
                    if r.status_code == 204:
                        replay_ids_in_group.append(data['id'])
                    else:
                        await ctx.send(":x: {} error: {}".format(r.status_code, r.json()['error']))
            except:
                await ctx.send(":x: {} error: {}".format(status_code, data['error']))
        
        return replay_ids_in_group
        
    async def _rename_replays(self, ctx, uploaded_replays_ids):
        auth_token = await self._get_auth_token(ctx.guild)
        renamed = []

        game_number = 1
        for replay_id in uploaded_replays_ids:
            endpoint = '/replays/{}'.format(replay_id)
            payload = {
                'title': 'Game {}'.format(game_number)
            }
            r = await self._bc_patch_request(ctx, endpoint, auth_token=auth_token, json=payload)
            status_code = r.status_code

            if status_code == 204:
                renamed.append(replay_id)            
            else:
                await ctx.send(":x: {} error.".format(status_code))

            game_number += 1
        return renamed

    def _delete_temp_files(self, files_to_upload):
        for replay_filename in files_to_upload:
            if os.path.exists("temp/{}".format(replay_filename)):
                os.remove("temp/{}".format(replay_filename))
        try:
            os.rmdir("temp") # Remove Temp Folder
        except OSError:
            print("Can't remove populated folder.")
            return False
        except:
            print("Uncaught error in delete_temp_files.")
            return False
        return True

    async def _get_tier_subgroup_name(self, ctx, tier):
        tier_num = (await self._get_tier_ranks(ctx))[tier]
        return '{}{}'.format(tier_num, tier)

    async def _get_all_match_players(self, ctx, match):
        players = []
        for team in ['home', 'away']:
            franchise_role, tier_role = await self.team_manager_cog._roles_for_team(ctx, match[team])
            team_members = self.team_manager_cog.members_from_team(ctx, franchise_role, tier_role)
            for player in team_members:
                players.append(player)
        return players

    # json db
    async def _get_auth_token(self, guild):
        return await self.config.guild(guild).AuthToken()
    
    async def _save_auth_token(self, ctx, token):
        await self.config.guild(ctx.guild).AuthToken.set(token)
        return True

    async def _get_top_level_group(self, ctx):
        return await self.config.guild(ctx.guild).TopLevelGroup()
    
    async def _save_top_level_group(self, ctx, group_id):
        await self.config.guild(ctx.guild).TopLevelGroup.set(group_id)
        return True
    
    async def _get_tier_ranks(self, ctx):
        return await self.config.guild(ctx.guild).TierRank()
    
    async def _save_tier_ranks(self, ctx, tier_ranks):
        await self.config.guild(ctx.guild).TierRanks.set(tier_ranks)
        return True

    async def _get_account_register(self):
        return await self.config.AccountRegister()
    
    async def _save_account_register(self, account_register):
        await self.config.AccountRegister.set(account_register)

    