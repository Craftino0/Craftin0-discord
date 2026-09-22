# type: ignore
import discord
from discord.ext import commands
import datetime

# الأيدي المسموح له بإدارة النظام واستثناءه من السولومود وقبول/رفض الاقتراحات
ALLOWED_USER_ID = 1471492990156410993

# قواميس التخزين المؤقت للإعدادات والسولومود لكل سيرفر
suggestion_settings = {}  # {guild_id: {"channel_id": id, "slowmode": seconds}}
user_cooldowns = {}      # {guild_id: {user_id: timestamp}}

# رابط الصورة المطلوبة لإرسالها في رسالة منفصلة بعد كل اقتراح
FIXED_IMAGE_URL = "https://cdn.discordapp.com/attachments/1389873114762055816/1505158779384234084/2026-05-16_134313.png?ex=6ab1b319&is=6ab06199&hm=95d1213e9e4c241147e8440c645661908331a642fb8031c3400763683b9b0326"


class ReasonModal(discord.ui.Modal):
    def __init__(self, action_type: str, message: discord.Message, guild_id: int):
        title = "سبب القبول" if action_type == "accept" else "سبب الرفض"
        super().__init__(title=title)
        self.action_type = action_type
        self.message = message
        self.guild_id = guild_id

    reason_input = discord.ui.TextInput(
        label="السبب",
        placeholder="اكتب سبب القبول أو الرفض هنا...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        # التحقق من الصلاحيات (الشخص المخصص أو صاحب السيرفر فقط)
        if interaction.user.id != ALLOWED_USER_ID and interaction.user != interaction.guild.owner:
            await interaction.response.send_message("❌ هذا الإجراء مخصص للشخص المخول لصاحب السيرفر فقط!", ephemeral=True)
            return

        # الرد أولاً على التفاعل لمنع خطأ انتهاء المهلة
        status_msg = "✅ تم قبول الاقتراح وتحديث حالته بنجاح." if self.action_type == "accept" else "❌ تم رفض الاقتراح وتحديث حالته بنجاح."
        await interaction.response.send_message(status_msg, ephemeral=True)

        embed = self.message.embeds[0]
        reason_text = self.reason_input.value

        # إزالة حقل الحالة القديم إن وجد لتفادي التكرار وتحديثه بشكل صحيح
        filtered_fields = [f for f in embed.fields if f.name != "حالة الاقتراح"]
        embed.clear_fields()
        for f in filtered_fields:
            embed.add_field(name=f.name, value=f.value, inline=f.inline)

        # تعديل اللون والحالة حسب نوع الإجراء
        if self.action_type == "accept":
            embed.color = discord.Color.green()  # يتحول للون الأخضر
            embed.add_field(
                name="حالة الاقتراح",
                value=f"✅ **تم القبول** بواسطة {interaction.user.mention}\n📌 **السبب:** {reason_text}",
                inline=False
            )
        else:
            embed.color = discord.Color.red()  # يتحول للون الأحمر
            embed.add_field(
                name="حالة الاقتراح",
                value=f"❌ **تم الرفض** بواسطة {interaction.user.mention}\n📌 **السبب:** {reason_text}",
                inline=False
            )

        # تحديث الرسالة باللون والحالة والسبب الجديد
        await self.message.edit(embed=embed, view=self.message.view)


class SuggestionModal(discord.ui.Modal, title="تقديم اقتراح جديد"):
    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    title_input = discord.ui.TextInput(
        label="عنوان الاقتراح",
        placeholder="اكتب عنواناً مختصراً لاقتراحك...",
        required=True,
        max_length=100
    )
    
    details_input = discord.ui.TextInput(
        label="تفاصيل الاقتراح",
        placeholder="اشرح اقتراحك بالتفصيل هنا...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )

    image_input = discord.ui.TextInput(
        label="رابط صورة (اختياري)",
        placeholder="ضع رابط صورة هنا إن وجد...",
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild_id = self.guild_id
        user_id = interaction.user.id
        current_time = datetime.datetime.now().timestamp()

        is_owner = interaction.user == interaction.guild.owner
        is_whitelisted = user_id == ALLOWED_USER_ID

        settings = suggestion_settings.get(guild_id)
        if settings and settings.get("slowmode", 0) > 0 and not (is_owner or is_whitelisted):
            slowmode_duration = settings["slowmode"]
            if guild_id in user_cooldowns and user_id in user_cooldowns[guild_id]:
                last_time = user_cooldowns[guild_id][user_id]
                elapsed = current_time - last_time
                if elapsed < slowmode_duration:
                    remaining = int(slowmode_duration - elapsed)
                    mins, secs = divmod(remaining, 60)
                    time_msg = f"{mins} دقيقة و {secs} ثانية" if mins > 0 else f"{secs} ثانية"
                    await interaction.response.send_message(
                        f"❌ عذراً، السولومود مفعل. يجب عليك الانتظار **{time_msg}** قبل إرسال اقتراح آخر.",
                        ephemeral=True
                    )
                    return

            if guild_id not in user_cooldowns:
                user_cooldowns[guild_id] = {}
            user_cooldowns[guild_id][user_id] = current_time

        channel_id = settings["channel_id"] if settings else None
        if not channel_id:
            await interaction.response.send_message("❌ لم يتم إعداد روم الاقتراحات في هذا السيرفر بعد!", ephemeral=True)
            return

        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message("❌ لم يتم العثور على روم الاقتراحات المحدد، يرجى إعادة إعداده.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"💡 {self.title_input.value}",
            description=self.details_input.value,
            color=0x2b2d31, # اللون الافتراضي قبل القبول أو الرفض
            timestamp=datetime.datetime.now()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"صاحب الاقتراح ID: {user_id}")

        img_url = self.image_input.value.strip()
        if img_url.startswith("http://") or img_url.startswith("https://"):
            embed.set_image(url=img_url)

        view = SuggestionAdminView(guild_id)
        
        # 1. إرسال رسالة الاقتراح أولاً
        msg = await channel.send(embed=embed, view=view)

        try:
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")
        except:
            pass

        try:
            await msg.create_thread(name=f"مناقشة اقتراح: {interaction.user.display_name}", auto_archive_duration=1440)
        except:
            pass

        # 2. إرسال الصورة في رسالة مستقلة بعدها مباشرة
        try:
            await channel.send(FIXED_IMAGE_URL)
        except:
            pass

        await interaction.response.send_message("✅ تم إرسال اقتراحك بنجاح إلى روم الاقتراحات!", ephemeral=True)


class SuggestionView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="اقترح", style=discord.ButtonStyle.secondary, emoji="💡", custom_id="open_suggestion_modal")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SuggestionModal(self.guild_id))


class SuggestionAdminView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="قبول", style=discord.ButtonStyle.success, emoji="✔️", custom_id="accept_suggestion")
    async def accept_sugg(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != ALLOWED_USER_ID and interaction.user != interaction.guild.owner:
            await interaction.response.send_message("❌ هذا الزر مخصص للشخص المخول لصاحب السيرفر فقط!", ephemeral=True)
            return
        await interaction.response.send_modal(ReasonModal("accept", interaction.message, self.guild_id))

    @discord.ui.button(label="رفض", style=discord.ButtonStyle.danger, emoji="✖️", custom_id="reject_suggestion")
    async def reject_sugg(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != ALLOWED_USER_ID and interaction.user != interaction.guild.owner:
            await interaction.response.send_message("❌ هذا الزر مخصص للشخص المخول لصاحب السيرفر فقط!", ephemeral=True)
            return
        await interaction.response.send_modal(ReasonModal("reject", interaction.message, self.guild_id))

    @discord.ui.button(label="تقديم اقتراح", style=discord.ButtonStyle.secondary, emoji="✍️", custom_id="inline_open_modal")
    async def inline_suggest(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SuggestionModal(self.guild_id))


class Suggestions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="set-sugg", description="إعداد روم الاقتراحات والسولومود")
    @discord.app_commands.describe(
        channel="حدد روم الاقتراحات",
        slowmode="حدد مدة السولومود بالثواني (0 للإلغاء)"
    )
    async def set_sugg(self, interaction: discord.Interaction, channel: discord.TextChannel, slowmode: int):
        if interaction.user.id != ALLOWED_USER_ID and interaction.user != interaction.guild.owner:
            await interaction.response.send_message("❌ عذراً، هذا الأمر مخصص **للشخص المخول** أو لصاحب السيرفر فقط!", ephemeral=True)
            return

        if slowmode < 0:
            await interaction.response.send_message("❌ لا يمكن أن يكون وقت السولومود بالسالب.", ephemeral=True)
            return

        guild_id = interaction.guild.id
        suggestion_settings[guild_id] = {
            "channel_id": channel.id,
            "slowmode": slowmode
        }

        view = SuggestionView(guild_id)
        embed = discord.Embed(
            title="📢 نظام الاقتراحات",
            description="اضغط على الزر أدناه لتقديم اقتراحك الجديد وسيتم مراجعته فوراً!",
            color=0x2b2d31
        )
        
        await channel.send(embed=embed, view=view)
        
        slowmode_text = f"{slowmode} ثانية" if slowmode > 0 else "مغلق"
        await interaction.response.send_message(
            f"✅ تم ضبط روم الاقتراحات بنجاح في {channel.mention}!\n⏱️ السولومود الحالي: **{slowmode_text}**",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(Suggestions(bot))