import os
import json
import asyncio
import datetime

import discord
from discord import app_commands
from discord.ext import commands

# ملف حفظ إعدادات كل سيرفر (مفعّل / مطفي)
SETTINGS_FILE = "data/autoback_settings.json"

# مدة الرجوع بالزمن للتراجع عن الأفعال (بالدقائق)
LOOKBACK_MINUTES = 15


def load_settings() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(data: dict) -> None:
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class AutoBack(commands.Cog):
    """
    نظام إصلاح تلقائي: عند طرد/حظر أي عضو، يتراجع البوت عن كل الأفعال
    التي قام بها ذلك العضو خلال آخر 15 دقيقة قبل طرده.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.settings = load_settings()

    # ---------- أدوات مساعدة للإعدادات ----------

    def is_enabled(self, guild_id: int) -> bool:
        return self.settings.get(str(guild_id), False)

    def set_enabled(self, guild_id: int, value: bool) -> None:
        self.settings[str(guild_id)] = value
        save_settings(self.settings)

    # ---------- أمر السلاش /auto back ----------

    auto_group = app_commands.Group(
        name="auto", description="أوامر نظام الحماية التلقائي"
    )

    @auto_group.command(
        name="back",
        description="تفعيل أو إطفاء الإصلاح التلقائي عند طرد/حظر عضو",
    )
    @app_commands.describe(الحالة="اختر تفعيل أو اطفاء")
    @app_commands.choices(
        الحالة=[
            app_commands.Choice(name="تفعيل", value="on"),
            app_commands.Choice(name="اطفاء", value="off"),
        ]
    )
    @app_commands.default_permissions(administrator=True)
    async def auto_back(
        self, interaction: discord.Interaction, الحالة: app_commands.Choice[str]
    ):
        if not interaction.guild:
            await interaction.response.send_message(
                "هذا الأمر يعمل داخل السيرفر فقط.", ephemeral=True
            )
            return

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ هذا الأمر مخصص للإداريين فقط.", ephemeral=True
            )
            return

        enabled = الحالة.value == "on"
        self.set_enabled(interaction.guild.id, enabled)

        if enabled:
            msg = (
                "✅ تم **تفعيل** نظام الإصلاح التلقائي.\n"
                f"من الآن، أي عضو يتم طرده أو حظره، سيتراجع البوت عن كل "
                f"ما فعله خلال آخر {LOOKBACK_MINUTES} دقيقة."
            )
        else:
            msg = "🔴 تم **إطفاء** نظام الإصلاح التلقائي."

        await interaction.response.send_message(msg, ephemeral=True)

    # ---------- استماع لأحداث الطرد والحظر ----------

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        if not self.is_enabled(guild.id):
            return

        # ننتظر قليلاً حتى يظهر السجل في الأوداتلوج
        await asyncio.sleep(2)

        # نتأكد أن هذا "طرد" فعلي وليس مغادرة اختيارية من العضو نفسه
        kicked = False
        try:
            async for entry in guild.audit_logs(
                limit=5, action=discord.AuditLogAction.kick
            ):
                if entry.target and entry.target.id == member.id:
                    age = (discord.utils.utcnow() - entry.created_at).total_seconds()
                    if age < 15:
                        kicked = True
                        break
        except discord.Forbidden:
            return

        if not kicked:
            return

        await self.revert_member_actions(guild, member)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        if not self.is_enabled(guild.id):
            return
        await self.revert_member_actions(guild, user)

    # ---------- المنطق الأساسي: البحث عن الأفعال والتراجع عنها ----------

    async def revert_member_actions(self, guild: discord.Guild, actor):
        cutoff = discord.utils.utcnow() - datetime.timedelta(
            minutes=LOOKBACK_MINUTES
        )

        entries = []
        try:
            async for entry in guild.audit_logs(after=cutoff, limit=300):
                if entry.user and entry.user.id == actor.id:
                    entries.append(entry)
        except discord.Forbidden:
            print("لا يملك البوت صلاحية عرض الأوداتلوج (View Audit Log).")
            return

        if not entries:
            return

        # الأقدم أولاً حتى يتم الإصلاح بنفس ترتيب حدوث الأفعال
        entries.sort(key=lambda e: e.created_at)

        for entry in entries:
            try:
                await self.handle_entry(guild, entry)
            except Exception as e:
                print(f"فشل التراجع عن الحدث {entry.action}: {e}")

    async def handle_entry(self, guild: discord.Guild, entry: discord.AuditLogEntry):
        A = discord.AuditLogAction
        action = entry.action
        before = entry.before
        after = entry.after

        # ================= القنوات =================
        if action == A.channel_create:
            channel = guild.get_channel(entry.target.id)
            if channel:
                await channel.delete(
                    reason="إصلاح تلقائي: قناة أنشأها عضو تم طرده/حظره"
                )

        elif action == A.channel_delete:
            ctype = getattr(before, "type", discord.ChannelType.text)
            name = getattr(before, "name", "restored-channel")
            category = None
            cat_ref = getattr(before, "category", None)
            if cat_ref:
                category = guild.get_channel(cat_ref.id)

            if ctype == discord.ChannelType.voice:
                await guild.create_voice_channel(
                    name=name,
                    category=category,
                    reason="إصلاح تلقائي: استعادة قناة صوتية محذوفة",
                )
            elif ctype == discord.ChannelType.category:
                await guild.create_category(
                    name=name, reason="إصلاح تلقائي: استعادة تصنيف محذوف"
                )
            else:
                await guild.create_text_channel(
                    name=name,
                    category=category,
                    reason="إصلاح تلقائي: استعادة قناة نصية محذوفة",
                )

        elif action == A.channel_update:
            channel = guild.get_channel(entry.target.id)
            if channel:
                changes = {}
                for attr in (
                    "name",
                    "topic",
                    "nsfw",
                    "slowmode_delay",
                    "bitrate",
                    "user_limit",
                    "position",
                ):
                    if hasattr(before, attr):
                        val = getattr(before, attr)
                        if val is not None:
                            changes[attr] = val
                if changes:
                    await channel.edit(
                        reason="إصلاح تلقائي: التراجع عن تعديل قناة", **changes
                    )

        # ================= الرتب =================
        elif action == A.role_create:
            role = guild.get_role(entry.target.id)
            if role:
                await role.delete(
                    reason="إصلاح تلقائي: رتبة أنشأها عضو تم طرده/حظره"
                )

        elif action == A.role_delete:
            await guild.create_role(
                name=getattr(before, "name", "restored-role"),
                colour=getattr(before, "colour", discord.Colour.default()),
                hoist=getattr(before, "hoist", False),
                mentionable=getattr(before, "mentionable", False),
                permissions=getattr(
                    before, "permissions", discord.Permissions.none()
                ),
                reason="إصلاح تلقائي: استعادة رتبة محذوفة",
            )

        elif action == A.role_update:
            role = guild.get_role(entry.target.id)
            if role:
                changes = {}
                for attr in ("name", "colour", "hoist", "mentionable", "permissions"):
                    if hasattr(before, attr):
                        val = getattr(before, attr)
                        if val is not None:
                            changes[attr] = val
                if changes:
                    await role.edit(
                        reason="إصلاح تلقائي: التراجع عن تعديل رتبة", **changes
                    )

        # ================= الأعضاء =================
        elif action == A.member_role_update:
            member = guild.get_member(entry.target.id)
            if member:
                before_roles = set(getattr(before, "roles", []) or [])
                after_roles = set(getattr(after, "roles", []) or [])
                added = after_roles - before_roles
                removed = before_roles - after_roles
                if added:
                    await member.remove_roles(
                        *added, reason="إصلاح تلقائي: التراجع عن إضافة رتب لعضو"
                    )
                if removed:
                    await member.add_roles(
                        *removed, reason="إصلاح تلقائي: التراجع عن سحب رتب من عضو"
                    )

        elif action == A.member_update:
            member = guild.get_member(entry.target.id)
            if member:
                if hasattr(before, "nick"):
                    try:
                        await member.edit(
                            nick=before.nick,
                            reason="إصلاح تلقائي: التراجع عن تغيير الاسم المستعار",
                        )
                    except Exception:
                        pass

                # اسم الخاصية يختلف حسب إصدار discord.py
                for attr_name in ("timed_out_until", "communication_disabled_until"):
                    if hasattr(before, attr_name):
                        try:
                            await member.edit(
                                timed_out_until=getattr(before, attr_name),
                                reason="إصلاح تلقائي: التراجع عن إسكات عضو",
                            )
                        except Exception:
                            pass
                        break

        elif action == A.ban:
            try:
                await guild.unban(
                    entry.target, reason="إصلاح تلقائي: التراجع عن حظر قام به عضو مطرود"
                )
            except Exception:
                pass

        elif action == A.kick:
            # لا يمكن للبوت إجبار عضو مطرود على العودة تلقائياً،
            # هذه الحالة تحتاج إرسال دعوة يدوياً إن رغب الإداري.
            pass

        # ================= الويبهوك =================
        elif action == A.webhook_create:
            try:
                webhooks = await guild.webhooks()
                for wh in webhooks:
                    if wh.id == entry.target.id:
                        await wh.delete(
                            reason="إصلاح تلقائي: التراجع عن إنشاء ويبهوك"
                        )
            except Exception:
                pass

        # ملاحظة: استعادة الإيموجي غير ممكنة تلقائياً لأن الأوداتلوج
        # لا يحتفظ بصورة الإيموجي الأصلية.


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoBack(bot))