import discord
from discord.ext import commands


class Public(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="مرحبا")
    async def hello(self, ctx):
        await ctx.send(f"أهلاً بك يا {ctx.author.name}!")


async def setup(bot):
    await bot.add_cog(Public(bot))