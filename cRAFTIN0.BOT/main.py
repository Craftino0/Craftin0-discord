import asyncio
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"تم تسجيل الدخول بنجاح! البوت شغال باسم: {bot.user}")
    try:
        # مزامنة أوامر السلاش مع دسكورد
        synced = await bot.tree.sync()
        print(f"تم مزامنة {len(synced)} أمر سلاش بنجاح.")
    except Exception as e:
        print(f"فشل مزامنة الأوامر: {e}")


# دالة تحميل الـ Cogs
async def load_extensions():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            ext_name = f"cogs.{filename[:-3]}"
            try:
                await bot.load_extension(ext_name)
                print(f"تم تحميل: {ext_name}")
            except Exception as e:
                print(f"فشل تحميل {ext_name}: {e}")

    mod_folder = "./cogs/moderation"
    if os.path.exists(mod_folder):
        for filename in os.listdir(mod_folder):
            if filename.endswith(".py"):
                ext_name = f"cogs.moderation.{filename[:-3]}"
                try:
                    await bot.load_extension(ext_name)
                    print(f"تم تحميل: {ext_name}")
                except Exception as e:
                    print(f"فشل تحميل {ext_name}: {e}")


async def main():
    async with bot:
        await load_extensions()
        await bot.start(TOKEN)


asyncio.run(main())