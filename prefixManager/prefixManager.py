import discord
import re
import ast

from discord.ext import commands
from cogs.utils import checks

class PrefixManager:
    """Used to set franchise and role prefixes and give to members in those franchises or with those roles"""

    DATASET = "PrefixData"
    PREFIXES_KEY = "Prefixes"

    def __init__(self, bot):
        self.bot = bot
        self.data_cog = self.bot.get_cog("RscData")

    @commands.command(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_server=True)
    async def addPrefixes(self, ctx, *prefixes_to_add):
        """Add the prefixes and corresponding GM name.

        Arguments:

        prefixes_to_add -- One or more teams in the following format:

        \t"['<gm_name>','<prefix>']"

        Each prefix should be separated by a space.

        Examples:

        \t[p]addPrefixes "['Shamu','STM']"
        \t[p]addPrefixes "['Shamu','STM']" "['Adammast','OCE']"

        """
        addedCount = 0
        try:
            for prefixStr in prefixes_to_add:
                prefix = ast.literal_eval(prefixStr)
                await self.bot.say("Adding prefix: {0}".format(repr(prefix)))
                prefixAdded = await self._add_prefix(ctx, *prefix)
                if prefixAdded:
                    addedCount += 1
        finally:
            await self.bot.say("Added {0} prefixes(s).".format(addedCount))
        await self.bot.say("Done.")

    @commands.command(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_server=True)
    async def addPrefix(self, ctx, gm_name: str, prefix: str):
        prefixAdded = await self._add_prefix(ctx, gm_name, prefix)
        if(prefixAdded):
            await self.bot.say("Done.")
        else:
            await self.bot.say("Error adding prefix: {0}".format(prefix))

    @commands.command(pass_context=True, no_pm=True)
    async def getPrefixes(self, ctx):
        """Used to get all prefixes in the prefix dictionary"""
        prefixes = self._prefixes(ctx)

        if(len(prefixes.items()) > 0):
            for key, value in prefixes.items():
                try:
                    await self.bot.say("Prefix for {0} = {1}".format(key, value))
                except IndexError:
                    await self.bot.say(":x: Error finding key value pair in prefix dictionary")
        else:
            await self.bot.say(":x: No prefixes are set in the dictionary")

    @commands.command(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_server=True)
    async def removePrefix(self, ctx, gm_name: str):
        """Used to remove a single prefix"""
        prefixes = self._prefixes(ctx)
        try:
            del prefixes[gm_name]
        except ValueError:
            await self.bot.say(
                "{0} does not have a prefix.".format(gm_name))
            return
        self._save_prefixes(ctx, prefixes)
        await self.bot.say("Done.")

    @commands.command(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_server=True)
    async def clearPrefixes(self, ctx):
        """Used to clear the prefix dictionary"""
        prefixes = self._prefixes(ctx)

        try:
            prefixes.clear()
            self._save_prefixes(ctx, prefixes)
            await self.bot.say(":white_check_mark: All prefixes have been removed from dictionary")
        except:
            await self.bot.say(":x: Something went wrong when trying to clear the prefix dictionary")

    @commands.command(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_server=True)
    async def lookupPrefix(self, ctx, gmName: str):
        prefixes = self._prefixes(ctx)

        try:
            prefix = prefixes[gmName]
            await self.bot.say("Prefix for {0} = {1}".format(gmName, prefix))
        except KeyError:
            await self.bot.say(":x: Prefix not found for {0}".format(gmName))

    def _find_role(self, ctx, role_id):
        server = ctx.message.server
        roles = server.roles
        for role in roles:
            if role.id == role_id:
                return role
        raise LookupError('No role with id: {0} found in server roles'.format(role_id))

    async def _add_prefix(self, ctx, gm_name: str, prefix: str):
        prefixes = self._prefixes(ctx)

        proper_gm_name = self._get_proper_gm_name(ctx, gm_name)

        # Validation of input
        # There are other validations we could do, but don't
        #     - that there aren't extra args
        errors = []
        if not proper_gm_name:
            errors.append("GM not found with name {0}.".format(gm_name))
        if not prefix:
            errors.append("Prefix not found from input for GM {0}.".format(gm_name))
        if errors:
            await self.bot.say(":x: Errors with input:\n\n  "
                               "* {0}\n".format("\n  * ".join(errors)))
            return

        try:
            prefixes[proper_gm_name] = prefix
        except:
            return False
        self._save_prefixes(ctx, prefixes)
        return True

    def _get_proper_gm_name(self, ctx, gm_name):
        server = ctx.message.server
        roles = server.roles
        for role in roles:
            try:
                gmNameFromRole = re.findall(r'(?<=\().*(?=\))', role.name)[0]
                if gmNameFromRole.lower() == gm_name.lower():
                    return gmNameFromRole
            except:
                continue

    def _all_data(self, ctx):
        return self.data_cog.load(ctx, self.DATASET)

    def _prefixes(self, ctx):
        all_data = self._all_data(ctx)
        prefixes = all_data.setdefault(self.PREFIXES_KEY, {})
        return prefixes

    def _save_prefixes(self, ctx, prefixes):
        all_data = self._all_data(ctx)
        all_data[self.PREFIXES_KEY] = prefixes
        self.data_cog.save(ctx, self.DATASET, all_data)

def setup(bot):
    bot.add_cog(PrefixManager(bot))