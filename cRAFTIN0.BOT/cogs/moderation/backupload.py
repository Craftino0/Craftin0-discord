import asyncio
import io
import json
import discord
from discord import app_commands
from discord.ext import commands

# الآي دي المسموح له استخدام أمر الـ Backup
ALLOWED_USER_ID = 1471492990156410993


class BackupLoadView(discord.ui.View):

  def __init__(self, backup_data: dict, user: discord.User):
    super().__init__(timeout=180)
    self.backup_data = backup_data
    self.user = user

  @discord.ui.button(
      label="تأكيد وبدء الاستعادة",
      style=discord.ButtonStyle.danger,
      emoji="⚠️",
  )
  async def confirm_load(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if interaction.user.id != ALLOWED_USER_ID:
      return await interaction.response.send_message(
          "غير مسموح لك استخدام هذا الزر.", ephemeral=True
      )

    guild = interaction.guild
    await interaction.response.send_message(
        "⏳ جاري بدء عملية استعادة السيرفر في الخلفية وحذف المحتوى القديم...",
        ephemeral=True,
    )

    # تعطيل الأزرار
    for child in self.children:
      child.disabled = True
    await interaction.message.edit(view=self)

    # رسالة التقدم في الخاص
    try:
      dm_channel = await self.user.create_dm()
      progress_msg = await dm_channel.send(
          "🚀 **بدء عملية استعادة السيرفر...**\n⏳ الوقت المتبقي المقدر: تقريباً دقيقة"
          " أو أقل...\n📊 النسبة: **0%**"
      )
    except Exception:
      progress_msg = None

    # مهمة التحديث كل 3 ثواني
    is_completed = False

    async def update_progress():
      percentages = [15, 35, 60, 85, 95]
      i = 0
      while not is_completed and i < len(percentages):
        await asyncio.sleep(3)
        if not is_completed and progress_msg:
          try:
            await progress_msg.edit(
                content=(
                    "🚀 **جاري استعادة السيرفر وتطبيق البيانات...**\n⏳ جاري"
                    f" التنفيذ...\n📊 النسبة: **{percentages[i]}%**"
                )
            )
          except Exception:
            pass
          i += 1

    progress_task = asyncio.create_task(update_progress())

    try:
      # 1. التنظيف والحذف الشامل (رومات، أقسام، رتب)
      for channel in guild.channels:
        try:
          await channel.delete()
          await asyncio.sleep(0.5)
        except Exception:
          pass

      for role in guild.roles:
        if (
            role != guild.default_role
            and not role.managed
            and role.position < guild.me.top_role.position
        ):
          try:
            await role.delete()
            await asyncio.sleep(0.7)
          except Exception:
            pass

      # 2. بناء الرتب الجديدة
      roles_data = self.backup_data.get("roles", [])
      role_mapping = {}

      roles_data = sorted(roles_data, key=lambda r: r.get("position", 0))

      for r_data in roles_data:
        if r_data["name"] == "@everyone":
          try:
            await guild.default_role.edit(
                permissions=discord.Permissions(r_data["permissions"]),
                color=discord.Color(r_data["color"]),
                hoist=r_data["hoist"],
                mentionable=r_data["mentionable"],
            )
            role_mapping[r_data["id"]] = guild.default_role
          except Exception:
            pass
          continue

        try:
          new_role = await guild.create_role(
              name=r_data["name"],
              permissions=discord.Permissions(r_data["permissions"]),
              color=discord.Color(r_data["color"]),
              hoist=r_data["hoist"],
              mentionable=r_data["mentionable"],
              reason="Server Backup Restoration",
          )
          role_mapping[r_data["id"]] = new_role
          await asyncio.sleep(1)
        except Exception:
          pass

      # 3. بناء الأقسام والرومات
      categories_data = self.backup_data.get("categories", [])
      channels_data = self.backup_data.get("channels", [])

      category_mapping = {}
      for cat_data in categories_data:
        try:
          overwrites = {}
          new_cat = await guild.create_category(
              name=cat_data["name"], overwrites=overwrites
          )
          category_mapping[cat_data["id"]] = new_cat
          await asyncio.sleep(1)
        except Exception:
          pass

      for ch_data in channels_data:
        try:
          category = (
              category_mapping.get(ch_data.get("category_id"))
              if ch_data.get("category_id")
              else None
          )
          if ch_data["type"] == "text":
            await guild.create_text_channel(
                name=ch_data["name"],
                category=category,
                topic=ch_data.get("topic"),
                slowmode_delay=ch_data.get("slowmode", 0),
            )
          elif ch_data["type"] == "voice":
            await guild.create_voice_channel(
                name=ch_data["name"],
                category=category,
                bitrate=ch_data.get("bitrate", 64000),
                user_limit=ch_data.get("user_limit", 0),
            )
          await asyncio.sleep(1)
        except Exception:
          pass

      is_completed = True
      progress_task.cancel()

      if progress_msg:
        try:
          await progress_msg.edit(
              content=(
                  "✅ **تمت عملية استعادة السيرفر بنجاح تام!**\n📊 النسبة:"
                  " **100%**\n🎉 تم بناء الرتب، الأقسام، والرومات وتفريغ القديم"
                  " بنجاح."
              )
          )
        except Exception:
          pass

    except Exception as e:
      is_completed = True
      progress_task.cancel()
      if progress_msg:
        try:
          await progress_msg.edit(
              content=f"❌ حدث خطأ أثناء تنفيذ الاستعادة: `{e}`"
          )
        except Exception:
          pass


class BackupLoadCog(commands.Cog):  # تم تعديل اسم الكلاس هنا لمنع التكرار

  def __init__(self, bot):
    self.bot = bot

  @app_commands.command(
      name="backup-load",
      description="استعادة السيرفر من ملف JSON وتحليل محتواه مسبقاً",
  )
  @app_commands.describe(file="قم برفع ملف الـ JSON الخاص بالباك أب هنا")
  async def backup_load(
      self, interaction: discord.Interaction, file: discord.Attachment
  ):
    if interaction.user.id != ALLOWED_USER_ID:
      return await interaction.response.send_message(
          "عذراً، هذا الأمر مخصص لصاحب البوت فقط.", ephemeral=True
      )

    if not file.filename.endswith(".json"):
      return await interaction.response.send_message(
          "❌ يرجى رفع ملف بصيغة `.json` صحيح.", ephemeral=True
      )

    try:
      file_bytes = await file.read()
      backup_data = json.loads(file_bytes.decode("utf-8"))
    except Exception:
      return await interaction.response.send_message(
          "❌ ملف الـ JSON تالف أو غير صالح للقرائة.", ephemeral=True
      )

    roles_count = len(backup_data.get("roles", []))
    categories_count = len(backup_data.get("categories", []))
    channels_count = len(backup_data.get("channels", []))
    server_name = backup_data.get("server_name", "غير معروف")

    analysis_embed = discord.Embed(
        title="📊 تحليل ملف الباك أب (Backup Analysis)",
        description=(
            "قام البوت بفحص الملف بنجاح وإليك التفاصيل الكاملة لما سيقوم به عند"
            " التأكيد:"
        ),
        color=discord.Color.blurple(),
    )
    analysis_embed.add_field(
        name="🏷️ اسم السيرفر الأصلي", value=f"`{server_name}`", inline=False
    )
    analysis_embed.add_field(
        name="👥 الرتب",
        value=f"سيتم إنشاء وترتيب **{roles_count}** رتبة.",
        inline=True,
    )
    analysis_embed.add_field(
        name="📁 الأقسام",
        value=f"سيتم إنشاء **{categories_count}** قسم.",
        inline=True,
    )
    analysis_embed.add_field(
        name="💬 الرومات",
        value=f"سيتم إنشاء **{channels_count}** روم (نصي وصوتي).",
        inline=True,
    )
    analysis_embed.add_field(
        name="⚠️ إجراء تحذيري خطير",
        value=(
            "**قبل اللصق:** سيتم حذف **جميع** الرومات، الأقسام، والرتب الحالية"
            " في السيرفر نهائياً وتفريغه بالكامل!"
        ),
        inline=False,
    )
    analysis_embed.set_footer(
        text=(
            "اضغط على الزر أدناه لتأكيد العملية وبدء التنفيذ مع إرسال التقدم"
            " للخاص."
        )
    )

    view = BackupLoadView(backup_data, interaction.user)
    await interaction.response.send_message(
        embed=analysis_embed, view=view, ephemeral=True
    )


async def setup(bot):
  await bot.add_cog(BackupLoadCog(bot))  # استخدام الاسم الجديد هنا أيضاً