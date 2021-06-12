import ast
import re

import discord
from discord.ext.commands import Context
from redbot.core import Config, checks, commands

defaults = {"Prefixes": {}}

class PrefixManager(commands.Cog):
    """Used to set franchise and role prefixes and give to members in those franchises or with those roles"""

    def __init__(self):
        self.config = Config.get_conf(self, identifier=1234567891, force_registration=True)
        self.config.register_guild(**defaults)

#region commmands

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def addPrefixes(self, ctx: Context, *prefixes_to_add):
        """Add the prefixes and corresponding GM name.

        Arguments:

        prefixes_to_add -- One or more prefixes in the following format:

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
                prefixAdded = await self.add_prefix(ctx, *prefix)
                if prefixAdded:
                    addedCount += 1
        finally:
            await ctx.send("Added {0} prefixes(s).".format(addedCount))
        await ctx.send("Done.")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def addPrefix(self, ctx: Context, gm_name: str, prefix: str):
        """Add a single prefix and corresponding GM name."""
        prefixAdded = await self.add_prefix(ctx, gm_name, prefix)
        if(prefixAdded):
            await ctx.send("Done.")
        else:
            await ctx.send("Error adding prefix: {0}".format(prefix))

    @commands.command(aliases=["listPrefixes", "prefixes"])
    @commands.guild_only()
    async def getPrefixes(self, ctx: Context):
        """Get all prefixes in the prefix dictionary"""
        prefixes = await self._prefixes(ctx.guild)

        if(len(prefixes.items()) > 0):
            message = "```Prefixes:"
            for key, value in prefixes.items():
                message += "\n\t{0} = {1}".format(key, value)
            message += "```"
            await ctx.send(message)
        else:
            await ctx.send(":x: No prefixes are set in the dictionary")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def removePrefix(self, ctx: Context, gm_name: str):
        """Remove a single prefix. The GM will no longer have a prefix in the dictionary"""
        prefixRemoved = await self.remove_prefix(ctx, gm_name)
        if(prefixRemoved):
            await ctx.send("Done.")
        else:
            await ctx.send("Error removing prefix for {0}".format(gm_name))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearPrefixes(self, ctx: Context):
        """Clear the prefix dictionary"""
        prefixes = await self._prefixes(ctx.guild)

        try:
            prefixes.clear()
            await self._save_prefixes(ctx.guild, prefixes)
            await ctx.send(":white_check_mark: All prefixes have been removed from dictionary")
        except:
            await ctx.send(":x: Something went wrong when trying to clear the prefix dictionary")

    @commands.command()
    @commands.guild_only()
    async def lookupPrefix(self, ctx: Context, gm_name: str):
        """Gets the prefix corresponding to the GM's franchise"""
        prefix = await self.get_gm_prefix(ctx.guild, gm_name)
        if(prefix):
            await ctx.send("Prefix for {0} = {1}".format(gm_name, prefix))
            return
        await ctx.send(":x: Prefix not found for {0}".format(gm_name))

    def _find_role(self, ctx: Context, role_id):
        guild = ctx.message.guild
        roles = guild.roles
        for role in roles:
            if role.id == role_id:
                return role
        raise LookupError('No role with id: {0} found in server roles'.format(role_id))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_nicknames=True)
    async def removeNicknames(self, ctx: Context, *userList):
        """Removes any nickname from every member that can be found from the userList"""
        empty = True
        removed = 0
        notFound = 0
        message = ""
        for user in userList:
            try:
                member = await commands.MemberConverter().convert(ctx, user)
                if member in ctx.guild.members:
                    await member.edit(nick=None)
                    removed += 1
                    empty = False
            except:
                if notFound == 0:
                    message += "Couldn't find:\n"
                message += "{0}\n".format(user)
                notFound += 1
        if empty:
            message += ":x: Nobody found from list"
        else:
           message += ":white_check_mark: Removed nicknames from everyone that was found from list"
        if notFound > 0:
            message += ". {0} user(s) were not found".format(notFound)
        if removed > 0:
            message += ". {0} user(s) had their nickname removed".format(removed)
        await ctx.send(message)

#endregion

#region helper methods

    async def add_prefix(self, ctx: Context, gm_name: str, prefix: str):
        prefixes = await self._prefixes(ctx.guild)

        proper_gm_name = self.get_proper_gm_name(ctx.guild, gm_name)

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
        await self._save_prefixes(ctx.guild, prefixes)
        return True

    async def remove_prefix(self, ctx: Context, gm_name: str):
        prefixes = await self._prefixes(ctx.guild)
        try:
            del prefixes[gm_name]
        except ValueError:
            await ctx.send("{0} does not have a prefix.".format(gm_name))
            return False
        await self._save_prefixes(ctx.guild, prefixes)
        return True

    def get_proper_gm_name(self, guild: discord.Guild, gm_name):
        for role in guild.roles:
            try:
                gmNameFromRole = re.findall(r'(?<=\().*(?=\))', role.name)[0]
                if gmNameFromRole.lower() == gm_name.lower():
                    return gmNameFromRole
            except:
                continue

    async def get_gm_prefix(self, guild: discord.Guild, gm_name):
        prefixes = await self._prefixes(guild)
        try:
            return prefixes[self.get_proper_gm_name(guild, gm_name)]
        except:
            return None

    async def get_franchise_prefix(self, guild: discord.Guild, franchise_role: discord.Role):
        prefixes = await self._prefixes(guild)
        try:
            gm_name = re.findall(r'(?<=\().*(?=\))', franchise_role.name)[0]
            return prefixes[gm_name]
        except:
            raise LookupError('GM name not found from role {0}'.format(franchise_role.name))

#endregion

#region load/save methods

    async def _prefixes(self, guild: discord.Guild):
        return await self.config.guild(guild).Prefixes()

    async def _save_prefixes(self, guild: discord.Guild, prefixes):
        await self.config.guild(guild).Prefixes.set(prefixes)

#endregion
