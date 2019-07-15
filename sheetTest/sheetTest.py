import discord
import gspread
import typing

from discord.ext import commands
from oauth2client.service_account import ServiceAccountCredentials

class SheetTest:
    """Test cog for accessing and editing a Google Sheet"""

    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    credentials = ServiceAccountCredentials.from_json_keyfile_name('data/sheetTest/Python Test-21ff839e46f8.json', scope)
    gc = gspread.authorize(credentials)

    def __init__(self, bot):
        self.bot = bot

    @commands.command(no_pm=True)
    async def test(self, ctx):
        """Edits the spreadsheet"""
        wks = self.gc.open('Test').sheet1
        await ctx.send(wks.get_all_records())

        wks.append_row(['This should go in column 1', 'This should go in column 2'])
        await ctx.send(wks.get_all_records())

    @commands.command(no_pm=True)
    async def read(self, ctx, rowIndex: int = None, columnIndex: int = None):
        """Reads data from the spreadsheet at the specified row and column, or reads all data if no row or column are specified."""
        wks = self.gc.open('Test').sheet1
        if(rowIndex and columnIndex):
            await ctx.send(wks.cell(rowIndex, columnIndex).value)
        else:
            await ctx.send(wks.get_all_records())

    @commands.command(no_pm=True)
    async def write(self, ctx, message, rowIndex: int = None, columnIndex: int = None):
        """Writes data to the spreadsheet at the specified row and column, or at the bottom of the sheet if no row or column are specified."""
        wks = self.gc.open('Test').sheet1
        if(rowIndex and columnIndex):
            wks.update_cell(rowIndex, columnIndex, message)
        else:
            wks.append_row([message])
        
       

def setup(bot):
    bot.add_cog(SheetTest(bot))