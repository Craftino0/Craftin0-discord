import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Select, View
import io
import json
import asyncio

# الآي دي المسموح له استخدام أمر الباك أب
ALLOWED_USER_ID = 1471492990156410993


class BackupSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="نسخ الرومات والأقسام",
                description="استخراج كافة الرومات والأقسام وصلاحياتها في ملف JSON",
                emoji="📁",
                value="channels"
            ),
            discord.SelectOption(
                label="نسخ الرتب والأعضاء",
                description="استخراج الرتب والأعضاء الذين يمتلكونها في ملف JSON",
                emoji="🎭",
                value="roles"
            ),
            discord.SelectOption(
                label="نسخ الإيموجي والستيكرات",
                description="تحميل روابط وإيموجي السيرفر في ملف بيانات",
                emoji="🎨",
                value="emojis"
            ),
            discord.SelectOption(
                label="نسخ رسائل السيرفر (HTML/TXT)",
                description="تصدير سجل رسائل الرومات الحالية إلى ملف نصي تفاعلي",
                emoji="📜",
                value="messages_html"
            ),
            discord.SelectOption(
                label="نسخ السيرفر بالكامل (Full Backup)",
                description="دمج وتصدير كل ما سبق حرفياً (رومات، رتب مع أعضائها، إيموجي، ورسائل) في ملف شامل",
                emoji="⚡",
                value="full_backup"
            ),
        ]
        super().__init__(placeholder="اختر نوع النسخ الاحتياطي الحقيقي...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        user = interaction.user

        if user.id != ALLOWED_USER_ID and user != interaction.guild.owner:
            await interaction.response.send_message("عذراً، هذا الأمر مخصص لصاحب البوت فقط! ❌", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        # دالة شريط التحميل المتحدث كل 3 ثوانٍ بشكل واقعي
        async def progress_simulation():
            steps = [
                (15, "⏳ جاري الاتصال بقاعدة بيانات السيرفر وجلب الهيكل..."),
                (40, "🔄 جاري فحص الرومات، الرتب، وأعضاء السيرفر..."),
                (70, "📦 جاري تجميع كافة العناصر وربط الرتب بالأعضاء في ملف JSON..."),
                (90, "📤 جاري تجهيز الملف للإرسال الفوري لرسائلك الخاصة...")
            ]
            for percent, text in steps:
                progress_bar = "█" * (percent // 10) + "░" * (10 - (percent // 10))
                embed = discord.Embed(
                    title="⏳ جاري تنفيذ النسخ الاحتياطي...",
                    description=f"{text}\n\n`[{progress_bar}] {percent}%`",
                    color=discord.Color.orange()
                )
                try:
                    await interaction.edit_original_response(embed=embed, view=None)
                except Exception:
                    pass
                await asyncio.sleep(3)

        task_progress = asyncio.create_task(progress_simulation())

        try:
            # 1. نسخ الرومات والأقسام
            if choice == "channels":
                channels_data = [{
                    "name": c.name,
                    "type": str(c.type),
                    "position": c.position,
                    "category": c.category.name if c.category else None
                } for c in guild.channels]
                
                file_bytes = json.dumps(channels_data, indent=4, ensure_ascii=False).encode('utf-8')
                file = discord.File(io.BytesIO(file_bytes), filename=f"channels_backup_{guild.name}.json")
                await user.send(f"📁 **نسخة الرومات والأقسام لسيرفر: {guild.name}**", file=file)

            # 2. نسخ الرتب والأعضاء (حفظ الرتبة مع أسماء أعضائها بشكل فعلي)
            elif choice == "roles":
                roles_data = [{
                    "role_name": r.name,
                    "role_id": r.id,
                    "color": str(r.color),
                    "position": r.position,
                    "members_count": len(r.members),
                    "members": [{"username": m.name, "id": m.id} for m in r.members]
                } for r in reversed(guild.roles)]

                file_bytes = json.dumps(roles_data, indent=4, ensure_ascii=False).encode('utf-8')
                file = discord.File(io.BytesIO(file_bytes), filename=f"roles_and_members_backup_{guild.name}.json")
                await user.send(f"🎭 **نسخة الرتب والأعضاء لسيرفر: {guild.name}**", file=file)

            # 3. نسخ الإيموجي والستيكرات
            elif choice == "emojis":
                emojis_data = {
                    "emojis": [{"name": e.name, "url": e.url} for e in guild.emojis],
                    "stickers": [{"name": s.name, "url": s.url} for s in guild.stickers]
                }
                file_bytes = json.dumps(emojis_data, indent=4, ensure_ascii=False).encode('utf-8')
                file = discord.File(io.BytesIO(file_bytes), filename=f"emojis_backup_{guild.name}.json")
                await user.send(f"🎨 **نسخة الإيموجي والستيكرات لسيرفر: {guild.name}**", file=file)

            # 4. نسخ الرسائل
            elif choice == "messages_html":
                messages_data = []
                async for message in interaction.channel.history(limit=50):
                    messages_data.append({
                        "author": str(message.author),
                        "content": message.content,
                        "created_at": str(message.created_at)
                    })
                file_bytes = json.dumps(messages_data, indent=4, ensure_ascii=False).encode('utf-8')
                file = discord.File(io.BytesIO(file_bytes), filename=f"messages_log_{interaction.channel.name}.json")
                await user.send(f"📜 **سجل رسائل روم #{interaction.channel.name}**", file=file)

            # 5. النسخ الشامل الكامل (كل ما سبق حرفياً + رتب الأعضاء)
            elif choice == "full_backup":
                channels_data = [{
                    "name": c.name,
                    "type": str(c.type),
                    "position": c.position,
                    "category": c.category.name if c.category else None
                } for c in guild.channels]

                # هنا تم إضافة حفظ الرتب مع أعضائها في النسخة الكاملة
                roles_data = [{
                    "role_name": r.name,
                    "role_id": r.id,
                    "color": str(r.color),
                    "position": r.position,
                    "members_count": len(r.members),
                    "members": [{"username": m.name, "id": m.id} for m in r.members]
                } for r in reversed(guild.roles)]

                emojis_data = [{"name": e.name, "url": e.url} for e in guild.emojis]
                stickers_data = [{"name": s.name, "url": s.url} for s in guild.stickers]

                messages_data = []
                async for message in interaction.channel.history(limit=50):
                    messages_data.append({
                        "author": str(message.author),
                        "content": message.content,
                        "created_at": str(message.created_at)
                    })

                full_server_data = {
                    "server_info": {
                        "server_name": guild.name,
                        "server_id": guild.id,
                        "owner": str(guild.owner),
                        "verification_level": str(guild.verification_level),
                        "channels_count": len(guild.channels),
                        "roles_count": len(guild.roles),
                        "emojis_count": len(guild.emojis),
                        "stickers_count": len(guild.stickers)
                    },
                    "channels": channels_data,
                    "roles_with_members": roles_data,
                    "emojis": emojis_data,
                    "stickers": stickers_data,
                    "recent_messages": messages_data
                }

                file_bytes = json.dumps(full_server_data, indent=4, ensure_ascii=False).encode('utf-8')
                file = discord.File(io.BytesIO(file_bytes), filename=f"full_server_backup_{guild.name}.json")
                await user.send(f"⚡ **النسخة الشاملة الكاملة (مع رتب الأعضاء) لسيرفر: {guild.name}**", file=file)

            if not task_progress.done():
                task_progress.cancel()

            success_embed = discord.Embed(
                title="✅ تمت العملية بنجاح!",
                description="تم استخراج كافة البيانات الشاملة (بما فيها الرتب والأعضاء) وتوليد الملف بصيغة JSON وإرساله إلى رسائلك الخاصة (DM) بنجاح تامة.",
                color=discord.Color.green()
            )
            await interaction.edit_original_response(embed=success_embed, view=None)

        except Exception as e:
            if not task_progress.done():
                task_progress.cancel()
            error_embed = discord.Embed(
                title="❌ حدث خطأ",
                description=f"حدث خطأ أثناء تنفيذ عملية النسخ: `{str(e)}`",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=error_embed, view=None)


class BackupView(View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(BackupSelect())


class BackupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="backup", description="لوحة النسخ الاحتياطي الحقيقي والشامل للسيرفر")
    async def backup_command(self, interaction: discord.Interaction):
        if interaction.user.id != ALLOWED_USER_ID and interaction.user != interaction.guild.owner:
            await interaction.response.send_message("عذراً، هذا الأمر مخصص لصاحب البوت فقط! ❌", ephemeral=True)
            return

        embed = discord.Embed(
            title="📦 نظام النسخ الاحتياطي الحقيقي (Active Backup)",
            description=(
                "مرحباً بك يا غالي.\n"
                "اختر نوع النسخ من القائمة أدناه، وسيقوم البوت **بجمع البيانات الفعليّة (شاملة رتب الأعضاء) وتوليد الملف وإرساله فوراً إلى رسائلك الخاصة (DM)**:"
            ),
            color=discord.Color.green()
        )
        embed.set_footer(text="Craftino Active Backup System")

        view = BackupView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(BackupCog(bot))