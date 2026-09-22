import asyncio
from datetime import datetime, timedelta
import os
import re
import discord
from discord import app_commands
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# تحميل المتغيرات والاتصال بـ MongoDB
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

client = AsyncIOMotorClient(MONGO_URI)
db = client["CRAFTINO_DB"]
anti_txt_collection = db["anti_txt_configs"]


async def load_config(guild_id: str):
    data = await anti_txt_collection.find_one({"_id": str(guild_id)})
    if data:
        return data
    return {
        "status": "off",
        "protection_type": "numbers_encryption",
        "whitelist_members": [],
        "whitelist_roles": [],
        "whitelist_channels": [],
        "log_channel": None,
    }


async def save_config(guild_id: str, data: dict):
    await anti_txt_collection.update_one(
        {"_id": str(guild_id)},
        {"$set": data},
        upsert=True
    )


class AntiTxtCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.recent_violations = {}

    @app_commands.command(
        name="anti-txt",
        description=(
            "إدارة وإعداد نظام منع التشفير (الأرقام، تنوع اللغة، الحروف المنفصلة،"
            " الرموز) والقائمة البيضاء"
        ),
    )
    @app_commands.choices(
        protection_type=[
            app_commands.Choice(
                name="تشفير الأرقام (Numbers Encryption)",
                value="numbers_encryption",
            ),
            app_commands.Choice(
                name="تشفير تنوع اللغة (Mixed Language Encryption)",
                value="mixed_language_encryption",
            ),
            app_commands.Choice(
                name="الحروف المنفصلة (Separated Letters)",
                value="separated_letters",
            ),
            app_commands.Choice(
                name="الرموز النصية (Symbols Encryption)",
                value="symbol_encryption",
            ),
        ],
        state=[
            app_commands.Choice(name="تفعيل (On)", value="on"),
            app_commands.Choice(name="إيقاف (Off)", value="off"),
        ],
        whitelist_action=[
            app_commands.Choice(name="لا شيء (None)", value="none"),
            app_commands.Choice(name="إضافة عضو (Add Member)", value="add_member"),
            app_commands.Choice(
                name="إزالة عضو (Remove Member)", value="remove_member"
            ),
            app_commands.Choice(name="إضافة رتبه (Add Role)", value="add_role"),
            app_commands.Choice(
                name="إزالة رتبه (Remove Role)", value="remove_role"
            ),
            app_commands.Choice(
                name="إضافة روم (Add Channel)", value="add_channel"
            ),
            app_commands.Choice(
                name="إزالة روم (Remove Channel)", value="remove_channel"
            ),
        ],
    )
    @app_commands.default_permissions(administrator=True)
    async def anti_txt(
        self,
        interaction: discord.Interaction,
        protection_type: str = "numbers_encryption",
        state: str = None,
        log_channel: discord.TextChannel = None,
        whitelist_action: str = "none",
        member: discord.Member = None,
        role: discord.Role = None,
        channel: discord.TextChannel = None,
    ):
        guild_id = str(interaction.guild.id)
        config = await load_config(guild_id)

        # تحديث نوع الحماية، الحالة، أو الروم إذا تم تحديدها
        if protection_type:
            config["protection_type"] = protection_type
        if state:
            config["status"] = state
        if log_channel:
            config["log_channel"] = log_channel.id

        response_messages = []

        if state or log_channel or protection_type:
            status_text = (
                "مفعل 🟢"
                if config["status"] == "on"
                else "مطفئ 🔴"
            )

            p_type_val = config.get("protection_type", "numbers_encryption")
            if p_type_val == "numbers_encryption":
                p_type_name = "تشفير الأرقام"
            elif p_type_val == "mixed_language_encryption":
                p_type_name = "تشفير تنوع اللغة"
            elif p_type_val == "separated_letters":
                p_type_name = "الحروف المنفصلة"
            else:
                p_type_name = "الرموز النصية وسط الكلمات"

            current_log = (
                interaction.guild.get_channel(config["log_channel"])
                if config["log_channel"]
                else None
            )
            log_text = current_log.mention if current_log else "غير محدد"
            response_messages.append(
                f"✅ **تم تحديث إعدادات النظام:**\n"
                f"• نوع الحماية: **{p_type_name}**\n"
                f"• الحالة: **{status_text}**\n"
                f"• روم اللوق: {log_text}"
            )

        # معالجة إجراءات القائمة البيضاء من نفس الأمر
        if whitelist_action != "none":
            if whitelist_action == "add_member":
                if not member:
                    await interaction.response.send_message(
                        "⚠️ يجب تحديد العضو المطلوب!", ephemeral=True
                    )
                    return
                w_list = config["whitelist_members"]
                m_id = str(member.id)
                if m_id not in w_list:
                    w_list.append(m_id)
                    response_messages.append(
                        f"✅ تم إضافة العضو `{member.name}` إلى القائمة البيضاء."
                    )
                else:
                    response_messages.append("⚠️ العضو موجود مسبقاً في القائمة البيضاء.")

            elif whitelist_action == "remove_member":
                if not member:
                    await interaction.response.send_message(
                        "⚠️ يجب تحديد العضو المطلوب!", ephemeral=True
                    )
                    return
                w_list = config["whitelist_members"]
                m_id = str(member.id)
                if m_id in w_list:
                    w_list.remove(m_id)
                    response_messages.append(
                        f"✅ تم إزالة العضو `{member.name}` من القائمة البيضاء."
                    )
                else:
                    response_messages.append("⚠️ العضو غير موجود في القائمة البيضاء.")

            elif whitelist_action == "add_role":
                if not role:
                    await interaction.response.send_message(
                        "⚠️ يجب تحديد الرتبة المطلوبة!", ephemeral=True
                    )
                    return
                w_list = config["whitelist_roles"]
                r_id = str(role.id)
                if r_id not in w_list:
                    w_list.append(r_id)
                    response_messages.append(
                        f"✅ تم إضافة الرتبة `{role.name}` إلى القائمة البيضاء."
                    )
                else:
                    response_messages.append("⚠️ الرتبة موجودة مسبقاً في القائمة البيضاء.")

            elif whitelist_action == "remove_role":
                if not role:
                    await interaction.response.send_message(
                        "⚠️ يجب تحديد الرتبة المطلوبة!", ephemeral=True
                    )
                    return
                w_list = config["whitelist_roles"]
                r_id = str(role.id)
                if r_id in w_list:
                    w_list.remove(r_id)
                    response_messages.append(
                        f"✅ تم إزالة الرتبة `{role.name}` من القائمة البيضاء."
                    )
                else:
                    response_messages.append("⚠️ الرتبة غير موجودة في القائمة البيضاء.")

            elif whitelist_action == "add_channel":
                if not channel:
                    await interaction.response.send_message(
                        "⚠️ يجب تحديد الروم المطلوب!", ephemeral=True
                    )
                    return
                w_list = config["whitelist_channels"]
                c_id = str(channel.id)
                if c_id not in w_list:
                    w_list.append(c_id)
                    response_messages.append(
                        f"✅ تم إضافة الروم {channel.mention} إلى القائمة البيضاء."
                    )
                else:
                    response_messages.append("⚠️ الروم موجود مسبقاً في القائمة البيضاء.")

            elif whitelist_action == "remove_channel":
                if not channel:
                    await interaction.response.send_message(
                        "⚠️ يجب تحديد الروم المطلوب!", ephemeral=True
                    )
                    return
                w_list = config["whitelist_channels"]
                c_id = str(channel.id)
                if c_id in w_list:
                    w_list.remove(c_id)
                    response_messages.append(
                        f"✅ تم إزالة الروم {channel.mention} من القائمة البيضاء."
                    )
                else:
                    response_messages.append("⚠️ الروم غير موجود في القائمة البيضاء.")

        await save_config(guild_id, config)

        if not response_messages:
            response_messages.append(
                "⚠️ لم تقم بتحديد أي إعداد أو إجراء لتعديله!"
            )

        await interaction.response.send_message(
            "\n\n".join(response_messages), ephemeral=True
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        guild_id = str(message.guild.id)
        config = await load_config(guild_id)

        if config.get("status") != "on":
            return

        # التحقق من القائمة البيضاء (عضو، رتبة، أو روم)
        if str(message.author.id) in config.get("whitelist_members", []):
            return
        if str(message.channel.id) in config.get("whitelist_channels", []):
            return

        if isinstance(message.author, discord.Member):
            user_role_ids = [str(r.id) for r in message.author.roles]
            if any(
                r_id in config.get("whitelist_roles", []) for r_id in user_role_ids
            ):
                return

        content = message.content
        matched = False
        current_protection = config.get(
            "protection_type", "numbers_encryption"
        )

        words = content.split()
        if current_protection == "numbers_encryption":
            for word in words:
                if re.search(
                    r"[\w\u0600-\u06FF].*?\d+.*?[\w\u0600-\u06FF]", word, re.UNICODE
                ):
                    if re.search(r"\d+", word):
                        matched = True
                        break
        elif current_protection == "mixed_language_encryption":
            for word in words:
                has_latin = bool(re.search(r"[a-zA-Z]", word))
                has_arabic = bool(re.search(r"[\u0600-\u06FF]", word))
                if has_latin and has_arabic:
                    matched = True
                    break
        elif current_protection == "separated_letters":
            if re.search(
                r"(?:[\w\u0600-\u06FF]\s+){2,}[\w\u0600-\u06FF]", content, re.UNICODE
            ):
                matched = True
        elif current_protection == "symbol_encryption":
            for word in words:
                if re.search(
                    r"[\w\u0600-\u06FF]+[^\w\s\u0600-\u06FF]+[\w\u0600-\u06FF]+",
                    word,
                    re.UNICODE,
                ):
                    matched = True
                    break

        if matched:
            try:
                await message.delete()
            except Exception:
                pass

            is_owner = message.author.id == message.guild.owner_id
            is_admin = message.author.guild_permissions.administrator
            action_taken = ""

            if current_protection == "numbers_encryption":
                violation_name = "التشفير بالأرقام"
            elif current_protection == "mixed_language_encryption":
                violation_name = "تشفير تنوع اللغة (خلط العربية والإنجليزية)"
            elif current_protection == "separated_letters":
                violation_name = "استخدام الحروف المنفصلة (أكثر من حرفين مفصولين)"
            else:
                violation_name = "استخدام الرموز النصية وسط الكلمات"

            try:
                warning_msg = await message.channel.send(
                    f"🚨 {message.author.mention} ممنوع {violation_name}!\n"
                    f"💬 **النص المخالف:** `{content}`"
                )
                asyncio.create_task(self.delete_after_delay(warning_msg, 4))
            except Exception:
                pass

            current_time = datetime.utcnow()
            user_key = (message.guild.id, message.author.id)
            is_timeout_applied = False

            if not is_admin and not is_owner:
                if user_key in self.recent_violations:
                    last_time = self.recent_violations[user_key]
                    if (current_time - last_time).total_seconds() <= 600:
                        try:
                            await message.author.timeout(
                                timedelta(minutes=20),
                                reason=f"تكرار مخالفة {violation_name}",
                            )
                            is_timeout_applied = True
                        except Exception:
                            pass

            self.recent_violations[user_key] = current_time
            action_taken = (
                "حذف الرسالة + تحذير ومنشن بالشات (يحذف بعد 4 ثوان)"
                + (" + تايم أوت 20 دقيقة (تكرار)" if is_timeout_applied else "")
            )

            log_channel_id = config.get("log_channel")
            if log_channel_id:
                log_channel = message.guild.get_channel(log_channel_id)
                if log_channel:
                    embed = discord.Embed(
                        title="🚨 رصد محاولة تشفير نصي (Anti-Txt)",
                        color=discord.Color.red(),
                        timestamp=datetime.utcnow(),
                    )
                    embed.add_field(
                        name="👤 العضو المخالف",
                        value=f"{message.author} (`{message.author.id}`)"
                        + (
                            " **[صاحب السيرفر 👑]**"
                            if is_owner
                            else (" **[أدمن]**" if is_admin else "")
                        ),
                        inline=False,
                    )
                    embed.add_field(
                        name="🛡️ نوع الحماية", value=violation_name, inline=True
                    )
                    embed.add_field(
                        name="📍 الروم", value=message.channel.mention, inline=True
                    )
                    embed.add_field(
                        name="⏱️ الإجراء المتخذ", value=action_taken, inline=False
                    )
                    embed.add_field(
                        name="💬 النص المخالف", value=f"```{content}```", inline=False
                    )
                    embed.set_footer(text=f"ID: {message.author.id}")
                    try:
                        await log_channel.send(embed=embed)
                    except Exception:
                        pass

    async def delete_after_delay(self, message: discord.Message, delay: int):
        await asyncio.sleep(delay)
        try:
            await message.delete()
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(AntiTxtCog(bot))