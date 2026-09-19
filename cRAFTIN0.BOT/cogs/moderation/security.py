import asyncio
import discord
from discord.ext import commands
from discord import app_commands

# الآي دي المسموح له استخدام أوامر اللوحة
ALLOWED_USER_ID = 1471492990156410993

# إعدادات الحماية (مفعلة تلقائياً لكل سيرفر، والعقوبة الافتراضية حظر)
protection_settings = {}


class SecurityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 1. أمر /anti server لتحديد العقوبة
    @app_commands.command(name="anti", description="إعدادات نظام الحماية والأمان للسيرفر")
    @app_commands.describe(action="اختر النظام أو الميزة التي تود ضبطها")
    @app_commands.choices(action=[
        app_commands.Choice(name="server (حماية اسم وصورة السيرفر)", value="server")
    ])
    @app_commands.describe(punishment="اختر العقوبة التلقائية عند محاولة التغيير")
    @app_commands.choices(punishment=[
        app_commands.Choice(name="حظر العضو (Ban)", value="ban"),
        app_commands.Choice(name="سحب الرتب", value="roles")
    ])
    async def anti_command(self, interaction: discord.Interaction, action: str, punishment: str):
        # التحقق من الصلاحية (أنت أو صاحب السيرفر فقط)
        if interaction.user.id != ALLOWED_USER_ID and interaction.user != interaction.guild.owner:
            await interaction.response.send_message("عذراً، هذا الأمر غير مخصص لك! ❌", ephemeral=True)
            return

        guild_id = interaction.guild.id
        
        # حفظ الإعدادات للسيرفر
        protection_settings[guild_id] = {
            "enabled": True,
            "punishment": punishment
        }

        punishment_name = "حظر العضو (Ban) 🔨" if punishment == "ban" else "سحب الرتب 🎭"
        
        await interaction.response.send_message(
            f"✅ **تم الحفظ بنجاح!**\n"
            f"🛡️ النظام: حماية اسم وصورة السيرفر\n"
            f"⚖️ العقوبة الجديدة: **{punishment_name}**",
            ephemeral=True
        )

    # 2. أمر /sett لعرض جميع إعدادات البوت باختصار
    @app_commands.command(name="sett", description="عرض جميع إعدادات وحالة الحماية في السيرفر باختصار")
    async def sett_command(self, interaction: discord.Interaction):
        if interaction.user.id != ALLOWED_USER_ID and interaction.user != interaction.guild.owner:
            await interaction.response.send_message("عذراً، هذا الأمر غير مخصص لك! ❌", ephemeral=True)
            return

        guild_id = interaction.guild.id
        settings = protection_settings.get(guild_id, {"enabled": True, "punishment": "ban"})
        
        status = "مفعلة ✅" if settings.get("enabled", True) else "متوقفة ❌"
        punishment_type = settings.get("punishment", "ban")
        punishment_name = "حظر العضو (Ban) 🔨" if punishment_type == "ban" else "سحب الرتب 🎭"

        await interaction.response.send_message(
            f"📊 **إعدادات البوت باختصار:**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔹 **حماية اسم وصورة السيرفر:** {status}\n"
            f"🔹 **العقوبة الحالية:** {punishment_name}\n"
            f"🔹 **الاسترجاع التلقائي:** مفعل فوري ⚡",
            ephemeral=True
        )

    # الحدث الفعلي للمراقبة والاسترجاع والعقاب
    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        settings = protection_settings.get(after.id, {"enabled": True, "punishment": "ban"})
        if not settings.get("enabled", True):
            return

        if before.name != after.name or before.icon != after.icon:
            try:
                # إرجاع الاسم والصورة فوراً
                await after.edit(
                    name=before.name,
                    icon=before.icon,
                    reason="حماية السيرفر: محاولة تغيير غير مصرح بها 🛡️"
                )

                await asyncio.sleep(0.4)
                changer = None
                async for entry in after.audit_logs(limit=2, action=discord.AuditLogAction.guild_update):
                    if entry.target.id == after.id:
                        changer = entry.user
                        break

                if changer and changer != self.bot.user and changer != after.owner and changer.id != ALLOWED_USER_ID:
                    punishment = settings.get("punishment", "ban")
                    if punishment == "ban":
                        await after.ban(changer, reason="محاولة تغيير اسم أو صورة السيرفر 🛡️")
                    elif punishment == "roles":
                        valid_roles = [r for r in changer.roles if r != after.default_role and r.position < after.me.top_role.position]
                        if valid_roles:
                            await changer.remove_roles(*valid_roles, reason="محاولة تغيير اسم أو صورة السيرفر 🛡️")
            except Exception as e:
                print(f"خطأ الحماية: {e}")

async def setup(bot):
    await bot.add_cog(SecurityCog(bot))