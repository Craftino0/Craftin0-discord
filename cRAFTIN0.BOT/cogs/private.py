import discord
from discord.ext import commands


class Private(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="خاص")
    @commands.has_permissions(administrator=True)
    async def special_cmd(self, ctx):
        await ctx.send("هذا أمر خاص للإدارة فقط!")


async def setup(bot):
    await bot.add_cog(Private(bot))