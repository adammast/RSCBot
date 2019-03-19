import discord
import gspread

from discord.ext import commands
from oauth2client.service_account import ServiceAccountCredentials

class SheetTest:
    """Test cog for accessing and editing a Google Sheet"""

    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    credentials = ServiceAccountCredentials.from_json_keyfile_name('data/sheetTest/Python Test-21ff839e46f8.json', scope)
    gc = gspread.authorize(credentials)

    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True, no_pm=True)
    async def test(self, ctx):
        """Edits the spreadsheet"""
        wks = self.gc.open('Test').sheet1
        await self.bot.say(wks.get_all_records())

        wks..append_row(['This should go in column 1', 'This should go in column 2'])
        await self.bot.say(wks.get_all_records())
        
       

def setup(bot):
    bot.add_cog(SheetTest(bot))