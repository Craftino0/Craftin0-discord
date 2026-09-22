import asyncio
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv


# =========================================================
# MONGODB
# =========================================================

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError("MONGO_URI غير موجود في ملف .env")

mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["CRAFTINO_DB"]
anti_server_collection = db["anti_server_configs"]


async def load_config(guild_id: str):
    data = await anti_server_collection.find_one({"_id": str(guild_id)})

    if data:
        return data

    return {
        "_id": str(guild_id),
        "enabled": False,
        "punishment": "ban",
        "threshold": 3,
        "duration": 60,
        "whitelist_role": None,
    }


async def save_config(guild_id: str, data: dict):
    data = dict(data)
    data.pop("_id", None)

    await anti_server_collection.update_one(
        {"_id": str(guild_id)},
        {"$set": data},
        upsert=True
    )


# =========================================================
# TIME PARSER
# =========================================================

def parse_duration(value: str):
    """
    Examples:
    30s
    1m
    2h
    1d
    """

    value = value.lower().strip()

    if len(value) < 2:
        return None

    unit = value[-1]

    try:
        number = float(value[:-1])
    except ValueError:
        return None

    if number <= 0:
        return None

    multipliers = {
        "s": 1,
        "m": 60,
        "h": 60 * 60,
        "d": 60 * 60 * 24,
    }

    if unit not in multipliers:
        return None

    return number * multipliers[unit]


def format_duration(seconds):
    seconds = int(seconds)

    if seconds % 86400 == 0:
        return f"{seconds // 86400}d"

    if seconds % 3600 == 0:
        return f"{seconds // 3600}h"

    if seconds % 60 == 0:
        return f"{seconds // 60}m"

    return f"{seconds}s"


# =========================================================
# ANTI SERVER
# =========================================================

class AntiServer(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        # guild_id -> executor_id -> list[timestamps]
        self.action_history = defaultdict(lambda: defaultdict(list))

        # guild_id -> last processed audit log IDs
        self.processed_entries = defaultdict(set)

        self.audit_monitor.start()

    def cog_unload(self):
        self.audit_monitor.cancel()

    # =====================================================
    # GET CONFIG
    # =====================================================

    async def get_guild_config(self, guild_id):
        return await load_config(str(guild_id))

    # =====================================================
    # WHITELIST CHECK
    # =====================================================

    def is_whitelisted(self, member: discord.Member, guild_config):

        whitelist_role_id = guild_config.get("whitelist_role")

        if not whitelist_role_id:
            return False

        role = member.guild.get_role(int(whitelist_role_id))

        if not role:
            return False

        return role in member.roles

    # =====================================================
    # SLASH COMMAND
    # /anti-server
    # =====================================================

    @app_commands.command(
        name="anti-server",
        description="إعداد نظام Anti-Server القائم على عدد إجراءات Audit Log"
    )
    @app_commands.describe(
        enabled="تفعيل أو تعطيل الحماية",
        punishment="العقوبة عند تجاوز الحد",
        threshold="عدد الإجراءات المسموح بها",
        duration="المدة مثل 30s أو 1m أو 2h",
        whitelist_role="رتبة الوايت ليست"
    )
    @app_commands.choices(
        enabled=[
            app_commands.Choice(name="تفعيل", value="on"),
            app_commands.Choice(name="إيقاف", value="off"),
        ],
        punishment=[
            app_commands.Choice(name="حظر Ban", value="ban"),
            app_commands.Choice(
                name="سحب الصلاحيات / إزالة الرتب",
                value="strip"
            ),
        ]
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def anti_server(
        self,
        interaction: discord.Interaction,
        enabled: app_commands.Choice[str],
        punishment: app_commands.Choice[str],
        threshold: app_commands.Range[int, 1, 1000],
        duration: str,
        whitelist_role: discord.Role | None = None
    ):

        guild = interaction.guild

        if guild is None:
            await interaction.response.send_message(
                "❌ هذا الأمر يعمل داخل السيرفر فقط.",
                ephemeral=True
            )
            return

        parsed_duration = parse_duration(duration)

        if parsed_duration is None:
            await interaction.response.send_message(
                "❌ صيغة الوقت غير صحيحة.\n\n"
                "أمثلة صحيحة:\n"
                "`30s`\n"
                "`1m`\n"
                "`2h`\n"
                "`1d`",
                ephemeral=True
            )
            return

        guild_config = await self.get_guild_config(guild.id)

        guild_config["enabled"] = enabled.value == "on"
        guild_config["punishment"] = punishment.value
        guild_config["threshold"] = int(threshold)
        guild_config["duration"] = parsed_duration
        guild_config["whitelist_role"] = (
            whitelist_role.id if whitelist_role else None
        )

        await save_config(guild.id, guild_config)

        # تنظيف السجل القديم للسيرفر
        self.action_history[guild.id].clear()

        embed = discord.Embed(
            title="🛡️ Anti-Server",
            description="تم تحديث إعدادات الحماية بنجاح.",
            color=discord.Color.green()
        )

        embed.add_field(
            name="الحالة",
            value="🟢 مفعلة" if guild_config["enabled"] else "🔴 متوقفة",
            inline=True
        )

        embed.add_field(
            name="العقوبة",
            value=(
                "🔨 Ban"
                if guild_config["punishment"] == "ban"
                else "🧹 سحب الصلاحيات"
            ),
            inline=True
        )

        embed.add_field(
            name="الحد",
            value=str(guild_config["threshold"]),
            inline=True
        )

        embed.add_field(
            name="المدة",
            value=format_duration(guild_config["duration"]),
            inline=True
        )

        embed.add_field(
            name="Whitelist",
            value=(
                whitelist_role.mention
                if whitelist_role
                else "لا توجد"
            ),
            inline=True
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    # =====================================================
    # /sett server
    # =====================================================

    @app_commands.command(
        name="sett-server",
        description="عرض إعدادات Anti-Server الحالية"
    )
    async def sett_server(self, interaction: discord.Interaction):

        guild = interaction.guild

        if guild is None:
            await interaction.response.send_message(
                "❌ هذا الأمر داخل السيرفر فقط.",
                ephemeral=True
            )
            return

        guild_config = await self.get_guild_config(guild.id)

        whitelist_role = guild_config.get("whitelist_role")

        role_text = "لا توجد"

        if whitelist_role:
            role = guild.get_role(int(whitelist_role))

            if role:
                role_text = role.mention
            else:
                role_text = "الرتبة غير موجودة"

        embed = discord.Embed(
            title="🛡️ Anti-Server Settings",
            description="الإعدادات الحالية لنظام الحماية.",
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="الحالة",
            value="🟢 مفعلة" if guild_config["enabled"] else "🔴 متوقفة",
            inline=False
        )

        embed.add_field(
            name="العقوبة",
            value=(
                "🔨 Ban"
                if guild_config["punishment"] == "ban"
                else "🧹 سحب الصلاحيات"
            ),
            inline=True
        )

        embed.add_field(
            name="عدد الإجراءات",
            value=str(guild_config["threshold"]),
            inline=True
        )

        embed.add_field(
            name="الفترة الزمنية",
            value=format_duration(guild_config["duration"]),
            inline=True
        )

        embed.add_field(
            name="Whitelist Role",
            value=role_text,
            inline=True
        )

        embed.add_field(
            name="طريقة العمل",
            value=(
                "النظام لا يهتم بنوع الإجراء.\n"
                "أي Audit Log Action يتم احتسابه كإجراء واحد."
            ),
            inline=False
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    # =====================================================
    # AUDIT LOG MONITOR
    # =====================================================

    @tasks.loop(seconds=3)
    async def audit_monitor(self):

        await self.bot.wait_until_ready()

        for guild in self.bot.guilds:

            guild_config = await self.get_guild_config(guild.id)

            if not guild_config["enabled"]:
                continue

            try:
                await self.check_guild_audit_logs(
                    guild,
                    guild_config
                )

            except discord.Forbidden:
                print(
                    f"[Anti-Server] لا يوجد صلاحية View Audit Log "
                    f"في {guild.name}"
                )

            except Exception as e:
                print(
                    f"[Anti-Server] Error in {guild.name}: {e}"
                )

    @audit_monitor.before_loop
    async def before_audit_monitor(self):
        await self.bot.wait_until_ready()

    # =====================================================
    # CHECK AUDIT LOG
    # =====================================================

    async def check_guild_audit_logs(
        self,
        guild: discord.Guild,
        guild_config
    ):

        now = datetime.now(timezone.utc)

        # نجلب آخر 50 Action
        entries = []

        async for entry in guild.audit_logs(limit=50):

            entries.append(entry)

        # نرتب من الأقدم للأحدث
        entries.reverse()

        for entry in entries:

            # لا يوجد Executor
            if not entry.user:
                continue

            executor = entry.user

            # البوت نفسه يتم تجاهله حتى لا يسجل عقوبته كإجراء جديد
            if self.bot.user and executor.id == self.bot.user.id:
                continue

            entry_id = entry.id

            # منع معالجة نفس الـ entry أكثر من مرة
            if entry_id in self.processed_entries[guild.id]:
                continue

            self.processed_entries[guild.id].add(entry_id)

            # منع الذاكرة من التضخم
            if len(self.processed_entries[guild.id]) > 500:
                self.processed_entries[guild.id] = set(
                    list(self.processed_entries[guild.id])[-250:]
                )

            # نحاول جلب Member
            member = guild.get_member(executor.id)

            if member is None:
                try:
                    member = await guild.fetch_member(executor.id)
                except Exception:
                    member = None

            if member is None:
                continue

            # =================================================
            # WHITELIST
            # =================================================

            if self.is_whitelisted(member, guild_config):
                continue

            # =================================================
            # RECORD ACTION
            # =================================================

            history = self.action_history[guild.id][executor.id]

            history.append({
                "timestamp": entry.created_at,
                "action": str(entry.action),
                "action_name": self.get_action_name(entry.action),
                "entry_id": entry.id
            })

            # =================================================
            # REMOVE OLD ACTIONS
            # =================================================

            cutoff = now - timedelta(
                seconds=guild_config["duration"]
            )

            history[:] = [
                action
                for action in history
                if action["timestamp"] >= cutoff
            ]

            # =================================================
            # CHECK THRESHOLD
            # =================================================

            if len(history) >= guild_config["threshold"]:

                actions_snapshot = list(history)

                # تصفير العداد فوراً حتى لا يتكرر العقاب
                self.action_history[guild.id][executor.id].clear()

                await self.take_action(
                    guild,
                    member,
                    guild_config,
                    actions_snapshot
                )

    # =====================================================
    # ACTION NAME
    # =====================================================

    def get_action_name(self, action):

        names = {
            discord.AuditLogAction.guild_update:
                "تعديل السيرفر",

            discord.AuditLogAction.channel_create:
                "إنشاء روم",

            discord.AuditLogAction.channel_delete:
                "حذف روم",

            discord.AuditLogAction.channel_update:
                "تعديل روم",

            discord.AuditLogAction.overwrite_create:
                "إنشاء Permission Overwrite",

            discord.AuditLogAction.overwrite_update:
                "تعديل Permission Overwrite",

            discord.AuditLogAction.overwrite_delete:
                "حذف Permission Overwrite",

            discord.AuditLogAction.kick:
                "طرد عضو",

            discord.AuditLogAction.member_prune:
                "Prune Members",

            discord.AuditLogAction.ban:
                "حظر عضو",

            discord.AuditLogAction.unban:
                "فك حظر عضو",

            discord.AuditLogAction.member_update:
                "تعديل عضو",

            discord.AuditLogAction.member_role_update:
                "تعديل رتب عضو",

            discord.AuditLogAction.role_create:
                "إنشاء رتبة",

            discord.AuditLogAction.role_delete:
                "حذف رتبة",

            discord.AuditLogAction.role_update:
                "تعديل رتبة",

            discord.AuditLogAction.webhook_create:
                "إنشاء Webhook",

            discord.AuditLogAction.webhook_delete:
                "حذف Webhook",

            discord.AuditLogAction.webhook_update:
                "تعديل Webhook",

            discord.AuditLogAction.emoji_create:
                "إنشاء Emoji",

            discord.AuditLogAction.emoji_delete:
                "حذف Emoji",

            discord.AuditLogAction.emoji_update:
                "تعديل Emoji",

            discord.AuditLogAction.integration_create:
                "إنشاء Integration",

            discord.AuditLogAction.integration_delete:
                "حذف Integration",

            discord.AuditLogAction.integration_update:
                "تعديل Integration",

            discord.AuditLogAction.stage_instance_create:
                "إنشاء Stage",

            discord.AuditLogAction.stage_instance_delete:
                "حذف Stage",

            discord.AuditLogAction.stage_instance_update:
                "تعديل Stage",

            discord.AuditLogAction.invite_create:
                "إنشاء Invite",

            discord.AuditLogAction.invite_delete:
                "حذف Invite",

            discord.AuditLogAction.message_delete:
                "حذف رسالة",

            discord.AuditLogAction.message_bulk_delete:
                "حذف رسائل جماعي",

            discord.AuditLogAction.thread_create:
                "إنشاء Thread",

            discord.AuditLogAction.thread_delete:
                "حذف Thread",

            discord.AuditLogAction.thread_update:
                "تعديل Thread",
        }

        return names.get(
            action,
            str(action).replace("AuditLogAction.", "")
        )

    # =====================================================
    # TAKE ACTION
    # =====================================================

    async def take_action(
        self,
        guild: discord.Guild,
        member: discord.Member,
        guild_config,
        actions
    ):

        punishment = guild_config["punishment"]

        action_lines = []

        for index, action in enumerate(actions, 1):

            action_lines.append(
                f"**{index}.** `{action['action_name']}`\n"
                f"الوقت: <t:{int(action['timestamp'].timestamp())}:R>\n"
                f"ID: `{action['entry_id']}`"
            )

        actions_text = "\n\n".join(action_lines)

        # =================================================
        # BAN
        # =================================================

        if punishment == "ban":

            result = "❌ فشل الحظر."

            # Owner لا يمكن حظره
            if member.id == guild.owner_id:

                result = (
                    "⚠️ العضو هو Owner السيرفر، "
                    "Discord يمنع البوت من حظره."
                )

            # Hierarchy
            elif member.top_role >= guild.me.top_role:

                result = (
                    "⚠️ لا يمكن حظر العضو بسبب "
                    "Role Hierarchy."
                )

            else:

                try:

                    await guild.ban(
                        member,
                        reason=(
                            "Anti-Server: تجاوز الحد المسموح "
                            f"({guild_config['threshold']} actions)"
                        ),
                        delete_message_seconds=0
                    )

                    result = "🔨 تم حظره بنجاح."

                except discord.Forbidden:

                    result = (
                        "❌ فشل الحظر: البوت لا يملك "
                        "صلاحية Ban Members."
                    )

                except Exception as e:

                    result = f"❌ فشل الحظر: `{e}`"

        # =================================================
        # STRIP
        # =================================================

        else:

            result = await self.strip_permissions(
                guild,
                member
            )

        # =================================================
        # DM OWNER
        # =================================================

        await self.notify_owner(
            guild,
            member,
            guild_config,
            actions,
            result
        )

        # =================================================
        # CONSOLE
        # =================================================

        print(
            "\n"
            "================ ANTI-SERVER ================\n"
            f"Guild: {guild.name} ({guild.id})\n"
            f"Executor: {member} ({member.id})\n"
            f"Actions: {len(actions)}\n"
            f"Threshold: {guild_config['threshold']}\n"
            f"Window: {format_duration(guild_config['duration'])}\n"
            f"Punishment: {punishment}\n"
            f"Result: {result}\n"
            "==============================================\n"
        )

    # =====================================================
    # STRIP PERMISSIONS
    # =====================================================

    async def strip_permissions(
        self,
        guild: discord.Guild,
        member: discord.Member
    ):

        if member.id == guild.owner_id:

            return (
                "⚠️ العضو هو Owner السيرفر، "
                "Discord يمنع إزالة صلاحياته."
            )

        if member.top_role >= guild.me.top_role:

            return (
                "⚠️ لا يمكن سحب رتب العضو بسبب "
                "Role Hierarchy."
            )

        removed_roles = []

        try:

            for role in member.roles:

                if role.is_default():
                    continue

                if role.managed:
                    continue

                if role >= guild.me.top_role:
                    continue

                try:
                    await member.remove_roles(
                        role,
                        reason="Anti-Server protection"
                    )

                    removed_roles.append(role.name)

                except discord.Forbidden:
                    continue

            if removed_roles:

                return (
                    "🧹 تم سحب رتب وصلاحيات العضو:\n"
                    + ", ".join(removed_roles)
                )

            return (
                "⚠️ لم يتم سحب أي رتبة. "
                "قد تكون الرتب أعلى من البوت أو Managed."
            )

        except Exception as e:

            return f"❌ حدث خطأ أثناء سحب الصلاحيات: `{e}`"

    # =====================================================
    # DM OWNER
    # =====================================================

    async def notify_owner(
        self,
        guild,
        member,
        guild_config,
        actions,
        result
    ):

        owner = guild.owner

        if owner is None:
            try:
                owner = await self.bot.fetch_user(guild.owner_id)
            except Exception:
                return

        action_lines = []

        for index, action in enumerate(actions, 1):

            timestamp = int(
                action["timestamp"].timestamp()
            )

            action_lines.append(
                f"**{index}.** `{action['action_name']}`\n"
                f"└ الوقت: <t:{timestamp}:F>\n"
                f"└ ID: `{action['entry_id']}`"
            )

        embed = discord.Embed(
            title="🚨 Anti-Server | Security Alert",
            description=(
                f"تم اكتشاف نشاط يتجاوز حد الحماية في "
                f"**{guild.name}**."
            ),
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(
            name="👤 الشخص",
            value=(
                f"{member.mention}\n"
                f"Username: `{member}`\n"
                f"ID: `{member.id}`"
            ),
            inline=False
        )

        embed.add_field(
            name="📊 عدد الإجراءات",
            value=(
                f"`{len(actions)}` / "
                f"`{guild_config['threshold']}`"
            ),
            inline=True
        )

        embed.add_field(
            name="⏱️ النافذة الزمنية",
            value=format_duration(
                guild_config["duration"]
            ),
            inline=True
        )

        embed.add_field(
            name="⚔️ العقوبة",
            value=(
                "Ban"
                if guild_config["punishment"] == "ban"
                else "Strip Permissions"
            ),
            inline=True
        )

        embed.add_field(
            name="📋 الإجراءات المسجلة",
            value="\n\n".join(action_lines)[:1024],
            inline=False
        )

        embed.add_field(
            name="🛡️ النتيجة",
            value=result,
            inline=False
        )

        embed.set_footer(
            text="Anti-Server Security System"
        )

        try:
            await owner.send(embed=embed)
        except discord.Forbidden:
            print(
                f"[Anti-Server] لا يمكن إرسال DM إلى Owner "
                f"في {guild.name}"
            )


async def setup(bot):
    await bot.add_cog(AntiServer(bot))