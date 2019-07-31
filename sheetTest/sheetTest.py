import discord
import gspread
import requests
import csv
import datetime
import os

from redbot.core import commands
from redbot.core import checks
from oauth2client.service_account import ServiceAccountCredentials
from discord import File

now = datetime.datetime.now()
readibletime =  now.strftime("%Y-%m-%d_%H-%M-%S")
Outputcsv = "%s.csv" % (readibletime)

class SheetTest(commands.Cog):
    """Test cog for accessing and editing a Google Sheet"""

    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    #credentials = ServiceAccountCredentials.from_json_keyfile_name('trackers-248415-645b0fa3512d.json', scope)
    #gc = gspread.authorize(credentials)

    @commands.guild_only()
    @commands.command()
    @checks.is_owner()
    async def testWrite(self, ctx):
        filepath = os.getcwd() + "/FileTest.csv"
        open(filepath, 'w', newline='')
        await ctx.send("Test File:", file=File(filepath))
        await ctx.send("Done")