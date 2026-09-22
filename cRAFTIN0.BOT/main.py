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
intents.voice_states = (
    True  # ضروري جداً لكي يتعرف البوت على الرومات الصوتية ويتصل بها
)

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


# دالة تحميل الـ Cogs بشكل تلقائي وشامل لجميع المجلدات الفرعية
async def load_extensions():
  cogs_root = "./cogs"
  if not os.path.exists(cogs_root):
    return

  for root, dirs, files in os.walk(cogs_root):
    for filename in files:
      if filename.endswith(".py"):
        # حساب المسار النسبي بالنسبة لمجلد cogs لتوليد اسم الـ Extension بدقة
        rel_path = os.path.relpath(os.path.join(root, filename), cogs_root)
        # تحويل المسار إلى صيغة نقطية مثل cogs.moderation.voiceauto
        ext_path = rel_path[:-3].replace(os.sep, ".")
        ext_name = f"cogs.{ext_path}"

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