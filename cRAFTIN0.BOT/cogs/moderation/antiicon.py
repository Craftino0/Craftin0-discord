import asyncio
import os
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv


# =========================================================
# Anti Icon / Anti Server Name
# =========================================================

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError("MONGO_URI غير موجود في ملف .env")

mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["CRAFTINO_DB"]
anti_icon_collection = db["anti_icon_configs"]


async def load_guild_data(guild_id: int) -> dict:
    guild_id = str(guild_id)

    data = await anti_icon_collection.find_one({"_id": guild_id})

    if data:
        data.pop("_id", None)
        return data

    return {
        "enabled": False,
        "punishment": "ban",
        "whitelist_role": None,
        "saved_name": None,
        "saved_icon": None,
    }


async def save_guild_data(guild_id: int, data: dict):
    guild_id = str(guild_id)

    data = dict(data)
    data.pop("_id", None)

    await anti_icon_collection.update_one(
        {"_id": guild_id},
        {"$set": data},
        upsert=True
    )



class AntiIcon(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.locks = {}

    async def get_guild_data(self, guild_id: int):
        return await load_guild_data(guild_id)

    # -----------------------------------------------------
    # -----------------------------------------------------
    # تحويل الأيقونة إلى Bytes
    # -----------------------------------------------------

    async def download_icon(self, guild: discord.Guild):
        if guild.icon is None:
            return None

        try:
            return await guild.icon.read()
        except Exception as e:
            print(f"[AntiIcon] فشل تحميل أيقونة السيرفر: {e}")
            return None

    # -----------------------------------------------------
    # فحص الـ Whitelist
    # -----------------------------------------------------

    def is_whitelisted(
        self,
        member: discord.Member,
        guild_data: dict
    ) -> bool:

        role_id = guild_data.get("whitelist_role")

        # لا توجد رتبة وايت ليست
        if not role_id:
            return False

        try:
            role_id = int(role_id)
        except (ValueError, TypeError):
            return False

        return any(role.id == role_id for role in member.roles)

    # -----------------------------------------------------
    # الحصول على منفذ التغيير من Audit Log
    # -----------------------------------------------------

    async def get_executor(
        self,
        guild: discord.Guild,
        before_name: str,
        before_icon: Optional[str],
        after_name: str,
        after_icon: Optional[str],
    ):
        try:
            async for entry in guild.audit_logs(
                limit=10,
                action=discord.AuditLogAction.guild_update
            ):
                # نتأكد أن التغيير حديث جدًا
                if (discord.utils.utcnow() - entry.created_at).total_seconds() > 15:
                    continue

                changes = entry.changes

                changed_name = False
                changed_icon = False

                for change in changes:
                    if change.attr == "name":
                        changed_name = True

                    elif change.attr == "icon":
                        changed_icon = True

                # تغيير الاسم أو الصورة أو الاثنين
                if changed_name or changed_icon:
                    return entry.user

        except discord.Forbidden:
            print(
                "[AntiIcon] البوت لا يملك صلاحية View Audit Log."
            )

        except Exception as e:
            print(f"[AntiIcon] خطأ في قراءة Audit Log: {e}")

        return None

    # -----------------------------------------------------
    # استرجاع اسم السيرفر
    # -----------------------------------------------------

    async def restore_name(
        self,
        guild: discord.Guild,
        saved_name: str
    ):
        if not saved_name:
            return

        if guild.name == saved_name:
            return

        try:
            await guild.edit(
                name=saved_name,
                reason="Anti Icon - Restore server name"
            )
        except discord.Forbidden:
            print(
                f"[AntiIcon] لا أملك صلاحية تعديل اسم السيرفر: {guild.id}"
            )
        except Exception as e:
            print(f"[AntiIcon] فشل استرجاع الاسم: {e}")

    # -----------------------------------------------------
    # استرجاع صورة السيرفر
    # -----------------------------------------------------

    async def restore_icon(
        self,
        guild: discord.Guild,
        saved_icon: Optional[str]
    ):
        try:
            if saved_icon:
                icon_bytes = bytes.fromhex(saved_icon)
            else:
                icon_bytes = None

            # إذا كانت الصورة الأصلية غير موجودة، نحذف الصورة الحالية.
            await guild.edit(
                icon=icon_bytes,
                reason="Anti Icon - Restore server icon"
            )

        except discord.Forbidden:
            print(
                f"[AntiIcon] لا أملك صلاحية تعديل صورة السيرفر: {guild.id}"
            )

        except Exception as e:
            print(f"[AntiIcon] فشل استرجاع صورة السيرفر: {e}")

    # -----------------------------------------------------
    # تطبيق العقوبة
    # -----------------------------------------------------

    async def punish(
        self,
        guild: discord.Guild,
        user: discord.User,
        guild_data: dict
    ):
        if user is None:
            return

        # البوت نفسه
        if user.id == self.bot.user.id:
            return

        member = guild.get_member(user.id)

        if member is None:
            try:
                member = await guild.fetch_member(user.id)
            except Exception:
                return

        # -------------------------------------------------
        # Whitelist
        # -------------------------------------------------

        if self.is_whitelisted(member, guild_data):
            print(
                f"[AntiIcon] {user} موجود في الـ Whitelist."
            )
            return

        punishment = guild_data.get("punishment", "ban")

        # -------------------------------------------------
        # Ban
        # -------------------------------------------------

        if punishment == "ban":

            try:
                await guild.ban(
                    member,
                    reason="Anti Icon - Unauthorized server change"
                )

                print(
                    f"[AntiIcon] تم حظر {user} من {guild.name}"
                )

            except discord.Forbidden:
                print(
                    f"[AntiIcon] لا أستطيع حظر {user}"
                )

            except Exception as e:
                print(
                    f"[AntiIcon] خطأ أثناء الحظر: {e}"
                )

        # -------------------------------------------------
        # سحب الرتب والصلاحيات
        # -------------------------------------------------

        elif punishment == "remove_roles":

            try:
                roles_to_remove = [
                    role
                    for role in member.roles
                    if role != guild.default_role
                    and role < guild.me.top_role
                ]

                if roles_to_remove:
                    await member.remove_roles(
                        *roles_to_remove,
                        reason="Anti Icon - Unauthorized server change"
                    )

                print(
                    f"[AntiIcon] تم سحب رتب {user}"
                )

            except discord.Forbidden:
                print(
                    f"[AntiIcon] لا أستطيع سحب رتب {user}"
                )

            except Exception as e:
                print(
                    f"[AntiIcon] خطأ أثناء سحب الرتب: {e}"
                )

    # -----------------------------------------------------
    # مراقبة تحديث السيرفر
    # -----------------------------------------------------

    @commands.Cog.listener()
    async def on_guild_update(
        self,
        before: discord.Guild,
        after: discord.Guild
    ):
        guild_data = await self.get_guild_data(after.id)

        # الميزة غير مفعلة
        if not guild_data.get("enabled", False):
            return

        # -------------------------------------------------
        # معرفة هل تغير الاسم
        # -------------------------------------------------

        name_changed = before.name != after.name

        # -------------------------------------------------
        # معرفة هل تغيرت الصورة
        # -------------------------------------------------

        before_icon = (
            before.icon.key if before.icon else None
        )

        after_icon = (
            after.icon.key if after.icon else None
        )

        icon_changed = before_icon != after_icon

        # لا يوجد تغيير مهم
        if not name_changed and not icon_changed:
            return

        # -------------------------------------------------
        # منع تداخل الأحداث
        # -------------------------------------------------

        if after.id in self.locks:
            return

        self.locks[after.id] = True

        try:

            # -------------------------------------------------
            # ننتظر لحظة حتى يظهر Audit Log
            # -------------------------------------------------

            await asyncio.sleep(1.0)

            # -------------------------------------------------
            # معرفة الشخص الذي قام بالتغيير
            # -------------------------------------------------

            executor = await self.get_executor(
                after,
                before.name,
                before_icon,
                after.name,
                after_icon
            )

            if executor is None:
                print(
                    f"[AntiIcon] لم أستطع تحديد منفذ التغيير في {after.name}"
                )

                # حتى لو لم نعرف المنفذ، نرجع السيرفر
                if name_changed:
                    await self.restore_name(
                        after,
                        guild_data.get("saved_name")
                    )

                if icon_changed:
                    await self.restore_icon(
                        after,
                        guild_data.get("saved_icon")
                    )

                return

            # -------------------------------------------------
            # هل الشخص Whitelisted؟
            # -------------------------------------------------

            member = after.get_member(executor.id)

            if member is None:
                try:
                    member = await after.fetch_member(executor.id)
                except Exception:
                    member = None

            whitelisted = False

            if member:
                whitelisted = self.is_whitelisted(
                    member,
                    guild_data
                )

            # -------------------------------------------------
            # إذا كان Whitelisted
            # نسمح بالتغيير ونحدث النسخة المحفوظة
            # -------------------------------------------------

            if whitelisted:

                print(
                    f"[AntiIcon] {executor} مسموح له بتغيير السيرفر."
                )

                # إذا غير الاسم
                if name_changed:
                    guild_data["saved_name"] = after.name

                # إذا غير الصورة
                if icon_changed:

                    new_icon = await self.download_icon(after)

                    if new_icon:
                        guild_data["saved_icon"] = (
                            new_icon.hex()
                        )
                    else:
                        guild_data["saved_icon"] = None

                await save_guild_data(after.id, guild_data)

                return

            # -------------------------------------------------
            # غير Whitelisted
            # نرجع الاسم والصورة أولاً
            # -------------------------------------------------

            print(
                f"[AntiIcon] تغيير غير مصرح به بواسطة {executor}"
            )

            # مهم:
            # الإصلاح يتم قبل العقوبة
            # -------------------------------------------------

            if name_changed:
                await self.restore_name(
                    after,
                    guild_data.get("saved_name")
                )

            if icon_changed:
                await self.restore_icon(
                    after,
                    guild_data.get("saved_icon")
                )

            # ننتظر حتى تنتهي عمليات الإصلاح
            await asyncio.sleep(1)

            # -------------------------------------------------
            # بعد الإصلاح نطبق العقوبة
            # -------------------------------------------------

            await self.punish(
                after,
                executor,
                guild_data
            )

        finally:
            await asyncio.sleep(1)
            self.locks.pop(after.id, None)

    # -----------------------------------------------------
    # Slash Command
    # -----------------------------------------------------

    @app_commands.command(
        name="anti-icon",
        description="حماية اسم وصورة السيرفر من التغيير غير المصرح به"
    )
    @app_commands.describe(
        status="تفعيل أو إيقاف Anti Icon",
        punishment="العقوبة عند التغيير غير المصرح به",
        whitelist_role="الرتبة المسموح لها بتغيير اسم وصورة السيرفر"
    )
    @app_commands.choices(
        status=[
            app_commands.Choice(
                name="تفعيل",
                value="on"
            ),
            app_commands.Choice(
                name="إيقاف",
                value="off"
            ),
        ],
        punishment=[
            app_commands.Choice(
                name="بان",
                value="ban"
            ),
            app_commands.Choice(
                name="سحب الرتب والصلاحيات",
                value="remove_roles"
            ),
        ]
    )
    @app_commands.default_permissions(administrator=True)
    async def anti_icon(
        self,
        interaction: discord.Interaction,
        status: app_commands.Choice[str],
        punishment: app_commands.Choice[str],
        whitelist_role: Optional[discord.Role] = None
    ):

        guild = interaction.guild

        if guild is None:
            await interaction.response.send_message(
                "❌ هذا الأمر يعمل داخل السيرفرات فقط.",
                ephemeral=True
            )
            return

        # -------------------------------------------------
        # التأكد من الصلاحيات
        # -------------------------------------------------

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ يجب أن تكون Administrator لاستخدام هذا الأمر.",
                ephemeral=True
            )
            return

        me = guild.me

        if me is None:
            await interaction.response.send_message(
                "❌ لم أستطع الحصول على بيانات البوت داخل السيرفر.",
                ephemeral=True
            )
            return

        missing = []

        if not me.guild_permissions.manage_guild:
            missing.append("Manage Server")

        if not me.guild_permissions.view_audit_log:
            missing.append("View Audit Log")

        if punishment.value == "ban":
            if not me.guild_permissions.ban_members:
                missing.append("Ban Members")

        if missing:
            await interaction.response.send_message(
                "❌ البوت يحتاج الصلاحيات التالية:\n\n"
                + "\n".join(f"• `{p}`" for p in missing),
                ephemeral=True
            )
            return

        # -------------------------------------------------
        # البيانات
        # -------------------------------------------------

        guild_data = await self.get_guild_data(guild.id)

        # -------------------------------------------------
        # إيقاف النظام
        # -------------------------------------------------

        if status.value == "off":

            guild_data["enabled"] = False
            await save_guild_data(guild.id, guild_data)

            embed = discord.Embed(
                title="🛡️ Anti Icon",
                description=(
                    "تم **إيقاف** حماية اسم وصورة السيرفر."
                ),
                color=discord.Color.red()
            )

            await interaction.response.send_message(
                embed=embed
            )

            return

        # -------------------------------------------------
        # تفعيل النظام
        # -------------------------------------------------

        # حفظ اسم السيرفر الحالي
        guild_data["saved_name"] = guild.name

        # حفظ صورة السيرفر الحالية
        icon_bytes = await self.download_icon(guild)

        if icon_bytes:
            guild_data["saved_icon"] = icon_bytes.hex()
        else:
            guild_data["saved_icon"] = None

        # حفظ العقوبة
        guild_data["punishment"] = punishment.value

        # حفظ رتبة الـ Whitelist
        if whitelist_role:
            guild_data["whitelist_role"] = whitelist_role.id
        else:
            guild_data["whitelist_role"] = None

        guild_data["enabled"] = True

        await save_guild_data(guild.id, guild_data)

        # -------------------------------------------------
        # اسم العقوبة
        # -------------------------------------------------

        if punishment.value == "ban":
            punishment_name = "🔨 بان"
        else:
            punishment_name = "🧹 سحب الرتب والصلاحيات"

        # -------------------------------------------------
        # اسم الرتبة
        # -------------------------------------------------

        if whitelist_role:
            whitelist_text = whitelist_role.mention
        else:
            whitelist_text = "لا توجد رتبة Whitelist"

        # -------------------------------------------------
        # Embed
        # -------------------------------------------------

        embed = discord.Embed(
            title="🛡️ Anti Icon",
            description=(
                "تم تفعيل حماية اسم وصورة السيرفر بنجاح."
            ),
            color=discord.Color.green()
        )

        embed.add_field(
            name="الحالة",
            value="🟢 مفعّل",
            inline=True
        )

        embed.add_field(
            name="العقوبة",
            value=punishment_name,
            inline=True
        )

        embed.add_field(
            name="Whitelist",
            value=whitelist_text,
            inline=False
        )

        embed.add_field(
            name="الحماية",
            value=(
                "📝 اسم السيرفر\n"
                "🖼️ صورة السيرفر"
            ),
            inline=False
        )

        embed.set_footer(
            text="سيتم إصلاح التغيير أولاً ثم تنفيذ العقوبة."
        )

        await interaction.response.send_message(
            embed=embed
        )


# =========================================================
# Setup
# =========================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(AntiIcon(bot))