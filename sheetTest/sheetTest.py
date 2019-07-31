import discord
import gspread
import requests
import csv
import datetime

from redbot.core import commands
from redbot.core import checks
from oauth2client.service_account import ServiceAccountCredentials

now = datetime.datetime.now()
readibletime =  now.strftime("%Y-%m-%d_%H-%M-%S")
Outputcsv = "Scrapes/%s.csv" % (readibletime)

class SheetTest(commands.Cog):
    """Test cog for accessing and editing a Google Sheet"""

    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    #credentials = ServiceAccountCredentials.from_json_keyfile_name('trackers-248415-645b0fa3512d.json', scope)
    #gc = gspread.authorize(credentials)

    @commands.guild_only()
    @commands.command()
    @checks.is_owner()
    async def testWrite(self, ctx):
        open(Outputcsv, 'w', newline='')

    # @commands.guild_only()
    # @commands.command()
    # @checks.is_owner()
    # async def read(self, ctx, rowIndex: int = None, columnIndex: int = None):
    #     """Reads data from the spreadsheet at the specified row and column, or reads all data if no row or column are specified."""
    #     wks = self.gc.open('Public Tracker List (Test)').sheet1
    #     if(rowIndex and columnIndex):
    #         await ctx.send(wks.cell(rowIndex, columnIndex).value)
    #     else:
    #         await ctx.send(wks.get_all_records())

    # @commands.guild_only()
    # @commands.command()
    # @checks.is_owner()
    # async def write(self, ctx, message, rowIndex: int = None, columnIndex: int = None):
    #     """Writes data to the spreadsheet at the specified row and column, or at the bottom of the sheet if no row or column are specified."""
    #     wks = self.gc.open('Test').sheet1
    #     if(rowIndex and columnIndex):
    #         wks.update_cell(rowIndex, columnIndex, message)
    #     else:
    #         wks.append_row([message])