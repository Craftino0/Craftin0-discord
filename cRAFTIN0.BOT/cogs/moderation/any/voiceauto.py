import os
import discord
from discord import app_commands
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# تحميل المتغيرات من ملف .env
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

# إنشاء الاتصال بقاعدة البيانات مباشرة
client = AsyncIOMotorClient(MONGO_URI)
db = client["CRAFTINO_DB"]
voice_collection = db["voice_auto_configs"]


# =========================================================
# MONGODB CONFIG
# =========================================================

async def load_config(guild_id: str):
    data = await voice_collection.find_one({"_id": str(guild_id)})
    if data:
        return data.get("channel_id")
    return None

async def save_config(guild_id: str, channel_id: int):
    await voice_collection.update_one(
        {"_id": str(guild_id)},
        {"$set": {"channel_id": channel_id}},
        upsert=True
    )


# =========================================================
# UI COMPONENTS
# =========================================================

class VoiceSelectDropdown(discord.ui.Select):

    def __init__(self, channels):
        options = []
        for channel in channels:
            options.append(
                discord.SelectOption(
                    label=channel.name,
                    value=str(channel.id),
                    description=f"ID: {channel.id}",
                    emoji="🔊",
                )
            )

        super().__init__(
            placeholder="اختر الروم الصوتي ليقوم البوت بالدخول إليه...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        channel_id = int(self.values[0])
        channel = interaction.guild.get_channel(channel_id)

        if not channel:
            return await interaction.response.send_message(
                "❌ الروم المحدد غير موجود.", ephemeral=True
            )

        try:
            if interaction.guild.voice_client:
                await interaction.guild.voice_client.move_to(channel)
            else:
                await channel.connect()

            # حفظ الإعدادات في MongoDB مباشرة
            await save_config(guild_id, channel_id)

            await interaction.response.send_message(
                f"✅ تم بنجاح اختيار والانضمام إلى الروم: **{channel.name}**\n💾 تم حفظ الإعدادات في قاعدة البيانات بنجاح.",
                ephemeral=True,
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ حدث خطأ أثناء محاولة الانضمام للروم: `{e}`", ephemeral=True
            )


class VoiceSelectView(discord.ui.View):

    def __init__(self, channels):
        super().__init__(timeout=60)
        self.add_item(VoiceSelectDropdown(channels))


# =========================================================
# COG
# =========================================================

class VoiceAutoCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            channel_id = await load_config(str(guild.id))
            if channel_id:
                channel = guild.get_channel(channel_id)
                if channel and isinstance(channel, discord.VoiceChannel):
                    try:
                        if guild.voice_client:
                            await guild.voice_client.move_to(channel)
                        else:
                            await channel.connect()
                        print(f"🔊 [Auto-Voice] تم الاتصال تلقائياً بروم '{channel.name}' في سيرفر '{guild.name}'")
                    except Exception as e:
                        print(f"❌ [Auto-Voice] فشل الاتصال التلقائي بالروم في سيرفر {guild.name}: {e}")

    @app_commands.command(
        name="voice-auto",
        description="اختر روم صوتي ليدخله البوت ويحفظه للاتصال التلقائي",
    )
    @app_commands.default_permissions(administrator=True)
    async def voice_auto(self, interaction: discord.Interaction):
        voice_channels = interaction.guild.voice_channels

        if not voice_channels:
            return await interaction.response.send_message(
                "❌ لا توجد أي رومات صوتية في هذا السيرفر!", ephemeral=True
            )

        view = VoiceSelectView(voice_channels)
        await interaction.response.send_message(
            "🎙️ **يرجى اختيار الروم الصوتي من القائمة أدناه:**",
            view=view,
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(VoiceAutoCog(bot))