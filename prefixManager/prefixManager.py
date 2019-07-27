import discord
import re
import ast

from redbot.core import Config
from redbot.core import commands
from cogs.utils import checks

defaults = {"Prefixes": {}}

class PrefixManager(commands.Cog):
    """Used to set franchise and role prefixes and give to members in those franchises or with those roles"""

    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567891, force_registration=True)
        self.config.register_guild(**defaults)

    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def addPrefixes(self, ctx, *prefixes_to_add):
        """Add the prefixes and corresponding GM name.

        Arguments:

        prefixes_to_add -- One or more teams in the following format:

        \t"['<gm_name>','<prefix>']"

        Each prefix should be separated by a space.

        Examples:

        \t[p]addPrefixes "['Adammast','OCE']"
        \t[p]addPrefixes "['Adammast','OCE']" "['Shamu','STM']"

        """
        addedCount = 0
        try:
            for prefixStr in prefixes_to_add:
                prefix = ast.literal_eval(prefixStr)
                await ctx.send("Adding prefix: {0}".format(repr(prefix)))
                prefixAdded = await self._add_prefix(ctx, *prefix)
                if prefixAdded:
                    addedCount += 1
        finally:
            await ctx.send("Added {0} prefixes(s).".format(addedCount))
        await ctx.send("Done.")

    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def addPrefix(self, ctx, gm_name: str, prefix: str):
        prefixAdded = await self._add_prefix(ctx, gm_name, prefix)
        if(prefixAdded):
            await ctx.send("Done.")
        else:
            await ctx.send("Error adding prefix: {0}".format(prefix))

    @commands.guild_only()
    async def getPrefixes(self, ctx):
        """Used to get all prefixes in the prefix dictionary"""
        prefixes = self._prefixes(ctx)

        if(len(prefixes.items()) > 0):
            message = "```Prefixes:"
            for key, value in prefixes.items():
                message += "\n\t{0} = {1}".format(key, value)
            message += "```"
            await ctx.send(message)
        else:
            await ctx.send(":x: No prefixes are set in the dictionary")

    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def removePrefix(self, ctx, gm_name: str):
        """Used to remove a single prefix"""
        prefixes = self._prefixes(ctx)
        try:
            del prefixes[gm_name]
        except ValueError:
            await ctx.send("{0} does not have a prefix.".format(gm_name))
            return
        self._save_prefixes(ctx, prefixes)
        await ctx.send("Done.")

    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearPrefixes(self, ctx):
        """Used to clear the prefix dictionary"""
        prefixes = self._prefixes(ctx)

        try:
            prefixes.clear()
            self._save_prefixes(ctx, prefixes)
            await ctx.send(":white_check_mark: All prefixes have been removed from dictionary")
        except:
            await ctx.send(":x: Something went wrong when trying to clear the prefix dictionary")

    @commands.guild_only()
    async def lookupPrefix(self, ctx, gmName: str):
        prefixes = self._prefixes(ctx)

        try:
            prefix = prefixes[gmName]
            await ctx.send("Prefix for {0} = {1}".format(gmName, prefix))
        except KeyError:
            await ctx.send(":x: Prefix not found for {0}".format(gmName))

    def _find_role(self, ctx, role_id):
        guild = ctx.message.guild
        roles = guild.roles
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
            await ctx.send(":x: Errors with input:\n\n  "
                               "* {0}\n".format("\n  * ".join(errors)))
            return

        try:
            prefixes[proper_gm_name] = prefix
        except:
            return False
        self._save_prefixes(ctx, prefixes)
        return True

    def _get_proper_gm_name(self, ctx, gm_name):
        guild = ctx.message.guild
        roles = guild.roles
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
        prefixes = await self.config.guild(ctx.guild).Prefixes()
        return prefixes

    def _save_prefixes(self, ctx, prefixes):
        await self.config.guild(ctx.guild).Prefixes.set(prefixes)

def setup(bot):
    bot.add_cog(PrefixManager(bot))