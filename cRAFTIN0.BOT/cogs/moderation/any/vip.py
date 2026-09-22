import os
import discord
from discord import app_commands
from discord.ext import commands, tasks
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI غير موجود في ملف .env")
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["CRAFTINO_DB"]
vip_configs = db["vip_configs"]
vip_members = db["vip_members"]
VIP_BASE_ROLE_ID = 1431705765797957673
CHECK_INTERVAL = 300
NO_VIP_MESSAGE = (
    "هذه المميزات مدفوعة، يمكنك شراء رتبة VIP أو دعم السيرفر ببوست، "
    "وفي بعض الأحيان تتوفر إنفايت يمكنك الاستفسار عن ذلك في التكت."
)
DEFAULT_TITLE = "✨ VIP"
DEFAULT_DESCRIPTION = "مميزات خاصة لأعضاء الـVIP.\nاختار الميزة من القائمة."
DEFAULT_EMBED_COLOR = 0x5865F2
COLOR_GROUPS = [
    ("🔴 الأحمر والوردي", [
        ("أحمر نقي", 0xFF0000), ("أحمر فاتح", 0xFF5252), ("أحمر مرجاني", 0xFF6F61),
        ("أحمر قرمزي", 0xDC143C), ("أحمر نبيذي", 0x8B0000), ("وردي", 0xFF4081),
        ("وردي فاتح", 0xFF80AB), ("وردي باستيل", 0xF8BBD0), ("وردي غامق", 0xC2185B),
        ("وردي فاقع", 0xE91E63), ("فوشيا", 0xFF00A8), ("ماجنتا", 0xD81B60),
        ("سالمون", 0xFA8072), ("خوخي", 0xFFAB91), ("كورال", 0xFF7F50),
        ("فراولة", 0xFF1744), ("روز", 0xF06292), ("طوبي", 0xBF360C),
        ("أحمر برتقالي", 0xFF3D00), ("مرجاني فاتح", 0xFF8A80), ("ورد غباري", 0xD8A0A6),
        ("وردي ناعم", 0xF48FB1), ("قرمزي فاتح", 0xEF5350), ("وردي داكن", 0xAD1457),
        ("وردي بنفسجي", 0xEC407A),
    ]),
    ("🟣 البنفسجي والأزرق", [
        ("بنفسجي", 0x9C27B0), ("بنفسجي غامق", 0x6A1B9A), ("بنفسجي ملكي", 0x7B1FA2),
        ("لافندر", 0xB39DDB), ("موف", 0xBA68C8), ("أرجواني فاتح", 0xCE93D8),
        ("أرجواني داكن", 0x4A148C), ("أرجواني كلاسيكي", 0x800080), ("نيلي", 0x3F51B5),
        ("نيلي غامق", 0x283593), ("بيروينكل", 0x7986CB), ("بنفسجي مزرق", 0x5C6BC0),
        ("أزرق", 0x2196F3), ("أزرق فاتح", 0x64B5F6), ("أزرق سماوي", 0x03A9F4),
        ("أزرق غامق", 0x1565C0), ("أزرق ملكي", 0x4169E1), ("أزرق كهربائي", 0x2979FF),
        ("أزرق ليلي", 0x191970), ("كحلي", 0x0D47A1), ("أزرق ألماسي", 0x00B0FF),
        ("أزرق ثلجي", 0xB3E5FC), ("أزرق ضبابي", 0x90CAF9), ("أزرق بترولي", 0x006064),
        ("أزرق فولاذي", 0x4682B4),
    ]),
    ("🟢 الأخضر والتركوازي", [
        ("أخضر", 0x4CAF50), ("أخضر فاتح", 0x81C784), ("أخضر غامق", 0x2E7D32),
        ("أخضر غابي", 0x1B5E20), ("أخضر زمردي", 0x00A86B), ("أخضر نعناعي", 0x00C853),
        ("نعناعي فاتح", 0xA5D6A7), ("أخضر عشبي", 0x43A047), ("أخضر صباري", 0x388E3C),
        ("أخضر زيتوني", 0x808000), ("زيتوني داكن", 0x33691E), ("كاكي", 0xBDB76B),
        ("تفاحي", 0x8BC34A), ("لايم", 0x76FF03), ("ليموني", 0xCDDC39),
        ("أخضر مائي", 0x80CBC4), ("تركوازي", 0x00ACC1), ("تيال", 0x009688),
        ("فيروزي", 0x1DE9B6), ("أكوا", 0x00FFFF), ("سماوي", 0x00BCD4),
        ("سماوي فاتح", 0x4DD0E1), ("أخضر مزرق", 0x26A69A), ("أخضر داكن", 0x004D40),
        ("نعناعي أزرق", 0x64FFDA),
    ]),
    ("🟠 الأصفر والبرتقالي والبني", [
        ("أصفر", 0xFFEB3B), ("أصفر فاتح", 0xFFF59D), ("أصفر دافئ", 0xFDD835),
        ("أصفر ذهبي", 0xFBC02D), ("ذهبي", 0xFFD700), ("ليموني ذهبي", 0xEEFF41),
        ("برتقالي", 0xFF9800), ("برتقالي فاتح", 0xFFB74D), ("برتقالي غامق", 0xEF6C00),
        ("برتقالي محروق", 0xE65100), ("مشمشي", 0xFFCC80), ("خوخي ذهبي", 0xFFB070),
        ("بني", 0x795548), ("بني غامق", 0x4E342E), ("شوكولاتة", 0x5D4037),
        ("قهوة", 0x6D4C41), ("بني عسلي", 0xA1887F), ("بني رمادي", 0x8D6E63),
        ("بيج", 0xD7CCC8), ("رملي", 0xD2B48C), ("كراميل", 0xA97142),
        ("نحاسي", 0xB87333), ("برونزي", 0xCD7F32), ("كهرماني", 0xFFBF00),
        ("زعفراني", 0xF4C430),
    ]),
    ("⚫ الأبيض والرمادي والدرجات الهادئة", [
        ("أبيض", 0xFFFFFF), ("عاجي", 0xFFFFF0), ("كريمي", 0xFFF8E1),
        ("رمادي فاتح جداً", 0xF5F5F5), ("فضي", 0xC0C0C0), ("رمادي فاتح", 0xBDBDBD),
        ("رمادي", 0x9E9E9E), ("رمادي متوسط", 0x757575), ("رمادي غامق", 0x424242),
        ("فحمي", 0x212121), ("أسود", 0x000000), ("رمادي مزرق", 0x546E7A),
        ("رمادي بنفسجي", 0x6D6875), ("رمادي أخضر", 0x607D5B), ("رمادي بني", 0x795548),
        ("وردي رمادي", 0xB08B8E), ("أزرق باهت", 0xBBDEFB), ("أخضر باهت", 0xC8E6C9),
        ("أصفر باهت", 0xFFF9C4), ("خوخي باهت", 0xFFE0B2), ("لافندر باهت", 0xE1BEE7),
        ("سماوي باهت", 0xB2EBF2), ("تركوازي باهت", 0xB2DFDB), ("بيج فاتح", 0xEFEBE9),
        ("وردي باهت", 0xFCE4EC),
    ]),
]
_seen_colors = set()
_clean_groups = []
for group_name, colors in COLOR_GROUPS:
    clean = []
    for label, value in colors:
        if value in _seen_colors:
            continue
        _seen_colors.add(value)
        clean.append((label, value))
    _clean_groups.append((group_name, clean))
COLOR_GROUPS = _clean_groups
EMBED_COLOR_CHOICES = [
    ("بنفسجي ديسكورد", 0x5865F2), ("أحمر", 0xFF0000), ("وردي", 0xFF4081),
    ("فوشيا", 0xFF00A8), ("بنفسجي", 0x9C27B0), ("لافندر", 0xB39DDB),
    ("أزرق", 0x2196F3), ("أزرق ملكي", 0x4169E1), ("سماوي", 0x00BCD4),
    ("تركوازي", 0x00ACC1), ("أخضر", 0x4CAF50), ("زمردي", 0x00A86B),
    ("لايم", 0x76FF03), ("أصفر", 0xFFEB3B), ("ذهبي", 0xFFD700),
    ("برتقالي", 0xFF9800), ("خوخي", 0xFFAB91), ("بني", 0x795548),
    ("شوكولاتة", 0x5D4037), ("أبيض", 0xFFFFFF), ("فضي", 0xC0C0C0),
    ("رمادي", 0x757575), ("فحمي", 0x212121), ("أسود", 0x000000),
    ("كحلي", 0x0D47A1),
]
async def get_config(guild_id: int):
    return await vip_configs.find_one({"_id": str(guild_id)})
async def save_config(guild_id: int, data: dict):
    await vip_configs.update_one(
        {"_id": str(guild_id)},
        {"$set": data},
        upsert=True,
    )
async def get_member_vip(guild_id: int, user_id: int):
    return await vip_members.find_one({"_id": f"{guild_id}:{user_id}"})
async def save_member_vip(guild_id: int, user_id: int, role_id: int, role_name: str, color: int):
    await vip_members.update_one(
        {"_id": f"{guild_id}:{user_id}"},
        {"$set": {
            "guild_id": guild_id,
            "user_id": user_id,
            "role_id": role_id,
            "role_name": role_name,
            "color": color,
        }},
        upsert=True,
    )
async def delete_member_vip(guild_id: int, user_id: int):
    await vip_members.delete_one({"_id": f"{guild_id}:{user_id}"})
def has_vip_access(member: discord.Member, config: dict) -> bool:
    allowed = set()
    for key in ("role_1_id", "role_2_id"):
        if config.get(key):
            try:
                allowed.add(int(config[key]))
            except (TypeError, ValueError):
                pass
    return any(role.id in allowed for role in member.roles)
def get_vip_role(guild: discord.Guild, data: dict | None):
    if not data or not data.get("role_id"):
        return None
    try:
        return guild.get_role(int(data["role_id"]))
    except (TypeError, ValueError):
        return None
def text_or_default(value: str | None, default: str, max_length: int = 80) -> str:
    value = (value or "").strip()
    return (value[:max_length] if value else default)
def emoji_or_default(value: str | None, default: str) -> str:
    value = (value or "").strip()
    return value[:32] if value else default
def build_vip_embed(guild: discord.Guild, config: dict) -> discord.Embed:
    embed = discord.Embed(
        title=config.get("embed_title") or DEFAULT_TITLE,
        description=config.get("embed_description") or DEFAULT_DESCRIPTION,
        color=discord.Color(int(config.get("embed_color", DEFAULT_EMBED_COLOR))),
    )
    if config.get("embed_image"):
        embed.set_image(url=config["embed_image"])
    thumbnail_url = config.get("embed_thumbnail") or (guild.icon.url if guild.icon else "")
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    embed.set_footer(text="VIP System")
    return embed
class NicknameModal(discord.ui.Modal, title="تغيير اسم العضو"):
    nickname = discord.ui.TextInput(
        label="الاسم الجديد",
        placeholder="اكتب الاسم الجديد...",
        max_length=32,
        required=True,
    )
    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ هذا الخيار يعمل داخل السيرفر فقط.", ephemeral=True)
            return
        config = await get_config(interaction.guild.id)
        if not config or not has_vip_access(interaction.user, config):
            await interaction.response.send_message(NO_VIP_MESSAGE, ephemeral=True)
            return
        me = interaction.guild.me
        if not me or not me.guild_permissions.manage_nicknames:
            await interaction.response.send_message("❌ البوت لا يملك Manage Nicknames.", ephemeral=True)
            return
        try:
            await interaction.user.edit(
                nick=str(self.nickname).strip(),
                reason="VIP - تغيير اسم العضو",
            )
            await interaction.response.send_message("✅ تم تغيير اسمك بنجاح.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ لا أستطيع تغيير اسمك، تأكد أن رتبتك أقل من رتبة البوت.", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ حصل خطأ: `{e}`", ephemeral=True)
class RoleNameModal(discord.ui.Modal):
    def __init__(self, cog, title: str):
        self.cog = cog
        super().__init__(title=title)
        self.role_name = discord.ui.TextInput(
            label="اسم الرتبة",
            placeholder="مثال: Craftino VIP",
            max_length=100,
            required=True,
        )
        self.add_item(self.role_name)
    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ هذا الخيار يعمل داخل السيرفر فقط.", ephemeral=True)
            return
        config = await get_config(interaction.guild.id)
        if not config or not has_vip_access(interaction.user, config):
            await interaction.response.send_message(NO_VIP_MESSAGE, ephemeral=True)
            return
        name = str(self.role_name).strip()
        if not name:
            await interaction.response.send_message("❌ اسم الرتبة لا يمكن أن يكون فارغاً.", ephemeral=True)
            return
        data = await get_member_vip(interaction.guild.id, interaction.user.id)
        existing_role = get_vip_role(interaction.guild, data)
        if self.title == "إنشاء رتبة خاصة":
            if existing_role:
                await interaction.response.send_message(
                    "ℹ️ لديك رتبة خاصة بالفعل. استخدم خيار تغيير اسم الرتبة أو تغيير لون الرتبة.",
                    ephemeral=True,
                )
                return
            await interaction.response.send_message(
                "🎨 اختر عائلة اللون ثم اللون المناسب:",
                view=RoleColorPickerView(self.cog, interaction.user, name, None, create_new=True),
                ephemeral=True,
            )
            return
        if not existing_role:
            await interaction.response.send_message(
                "❌ ليس لديك رتبة خاصة حالياً. استخدم إنشاء رتبة خاصة أولاً.", ephemeral=True
            )
            return
        me = interaction.guild.me
        if not me or existing_role >= me.top_role:
            await interaction.response.send_message(
                "❌ لا أستطيع تعديل هذه الرتبة بسبب ترتيب الرتب.", ephemeral=True
            )
            return
        try:
            await existing_role.edit(
                name=name,
                hoist=bool(config.get("role_hoist", False)),
                reason="VIP - تغيير اسم الرتبة الخاصة",
            )
            color = int(data.get("color", existing_role.color.value)) if data else existing_role.color.value
            await save_member_vip(interaction.guild.id, interaction.user.id, existing_role.id, name, color)
            await interaction.response.send_message(
                f"✅ تم تغيير اسم الرتبة إلى **{name}**.", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message("❌ البوت لا يملك صلاحية تعديل هذه الرتبة.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ حصل خطأ: `{e}`", ephemeral=True)
class RoleColorSelect(discord.ui.Select):
    def __init__(self, cog, member, role_name, existing_role, group_index, create_new=False):
        self.cog = cog
        self.member = member
        self.role_name = role_name
        self.existing_role = existing_role
        self.create_new = create_new
        group_name, colors = COLOR_GROUPS[group_index]
        options = [
            discord.SelectOption(
                label=label[:100],
                value=str(value),
                description=f"#{value:06X}",
            )
            for label, value in colors
        ]
        super().__init__(
            placeholder=group_name,
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"vip_color_group_{group_index}_{'create' if create_new else 'edit'}",
        )
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message("❌ هذه القائمة ليست لك.", ephemeral=True)
            return
        if not interaction.guild:
            await interaction.response.send_message("❌ هذا الخيار يعمل داخل السيرفر فقط.", ephemeral=True)
            return
        config = await get_config(interaction.guild.id)
        if not config or not has_vip_access(self.member, config):
            await interaction.response.edit_message(content=NO_VIP_MESSAGE, view=None)
            return
        await self.cog.apply_role_color(
            interaction,
            self.member,
            self.role_name,
            int(self.values[0]),
            self.existing_role,
            self.create_new,
        )
class RoleColorPickerView(discord.ui.View):
    def __init__(self, cog, member, role_name, existing_role, create_new=False):
        super().__init__(timeout=180)
        for index in range(len(COLOR_GROUPS)):
            self.add_item(
                RoleColorSelect(
                    cog, member, role_name, existing_role, index, create_new=create_new
                )
            )
class VIPMenu(discord.ui.Select):
    def __init__(self, cog, config=None):
        config = config or {}
        self.cog = cog
        options = [
            discord.SelectOption(
                label=text_or_default(config.get("nickname_label"), "تغيير اسم العضو"),
                value="nickname",
                emoji=emoji_or_default(config.get("nickname_emoji"), "✏️"),
                description="تغيير اسمك داخل السيرفر",
            ),
            discord.SelectOption(
                label=text_or_default(config.get("create_role_label"), "إنشاء رتبة خاصة"),
                value="create_role",
                emoji=emoji_or_default(config.get("create_role_emoji"), "🎨"),
                description="إنشاء رتبتك الخاصة لأول مرة",
            ),
            discord.SelectOption(
                label=text_or_default(config.get("role_name_label"), "تغيير اسم الرتبة"),
                value="role_name",
                emoji=emoji_or_default(config.get("role_name_emoji"), "🏷️"),
                description="تغيير اسم رتبتك الخاصة فقط",
            ),
            discord.SelectOption(
                label=text_or_default(config.get("role_color_label"), "تغيير لون الرتبة"),
                value="role_color",
                emoji=emoji_or_default(config.get("role_color_emoji"), "🌈"),
                description="تغيير لون رتبتك الخاصة فقط",
            ),
        ]
        super().__init__(
            placeholder=text_or_default(config.get("menu_placeholder"), "اختر الميزة التي تريد استخدامها"),
            min_values=1,
            max_values=1,
            options=options,
            custom_id="vip_system_menu",
        )
    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("❌ هذا النظام يعمل داخل السيرفر فقط.", ephemeral=True)
            return
        member = interaction.user
        if not isinstance(member, discord.Member):
            member = interaction.guild.get_member(interaction.user.id)
        if not member:
            await interaction.response.send_message("❌ لم أستطع العثور عليك داخل السيرفر.", ephemeral=True)
            return
        config = await get_config(interaction.guild.id)
        if not config or not has_vip_access(member, config):
            await interaction.response.send_message(NO_VIP_MESSAGE, ephemeral=True)
            return
        action = self.values[0]
        data = await get_member_vip(interaction.guild.id, member.id)
        existing_role = get_vip_role(interaction.guild, data)
        if action == "nickname":
            await interaction.response.send_modal(NicknameModal())
            return
        if action == "create_role":
            if existing_role:
                await interaction.response.send_message(
                    "ℹ️ لديك رتبة خاصة بالفعل. استخدم تغيير اسم الرتبة أو تغيير لون الرتبة.",
                    ephemeral=True,
                )
                return
            await interaction.response.send_modal(RoleNameModal(self.cog, "إنشاء رتبة خاصة"))
            return
        if action == "role_name":
            if not existing_role:
                await interaction.response.send_message(
                    "❌ ليس لديك رتبة خاصة حالياً. استخدم إنشاء رتبة خاصة أولاً.", ephemeral=True
                )
                return
            await interaction.response.send_modal(RoleNameModal(self.cog, "تغيير اسم الرتبة"))
            return
        if action == "role_color":
            if not existing_role:
                await interaction.response.send_message(
                    "❌ ليس لديك رتبة خاصة حالياً. استخدم إنشاء رتبة خاصة أولاً.", ephemeral=True
                )
                return
            await interaction.response.send_message(
                "🌈 اختر عائلة اللون ثم اللون المناسب:",
                view=RoleColorPickerView(
                    self.cog, member, existing_role.name, existing_role, create_new=False
                ),
                ephemeral=True,
            )
class VIPView(discord.ui.View):
    def __init__(self, cog, config=None):
        super().__init__(timeout=None)
        self.add_item(VIPMenu(cog, config))
class VIPCog(commands.Cog):
    set_group = app_commands.Group(name="set", description="إعدادات السيرفر")
    edit_group = app_commands.Group(name="edit", description="تعديل إعدادات السيرفر")
    def __init__(self, bot):
        self.bot = bot
    def cog_unload(self):
        self.vip_checker.cancel()
    @set_group.command(name="vip", description="إعداد نظام VIP")
    @app_commands.describe(
        channel="روم رسالة VIP",
        role_1="الرتبة الأولى المسموح لها",
        role_2="الرتبة الثانية المسموح لها",
        embed_title="عنوان الـEmbed - اتركه فارغاً للقالب الجاهز",
        embed_description="رسالة الـEmbed - اتركها فارغة للقالب الجاهز",
        embed_image="رابط الصورة الكبيرة للـEmbed",
        embed_thumbnail="رابط صورة البروفايل/Thumbnail للـEmbed",
        embed_color="لون الـEmbed",
        role_hoist="هل تظهر رتبة العضو بشكل منفصل؟",
        menu_placeholder="النص أعلى قائمة المميزات",
        nickname_label="اسم خيار تغيير اسم العضو",
        nickname_emoji="إيموجي خيار تغيير اسم العضو",
        create_role_label="اسم خيار إنشاء الرتبة",
        create_role_emoji="إيموجي خيار إنشاء الرتبة",
        role_name_label="اسم خيار تغيير اسم الرتبة",
        role_name_emoji="إيموجي خيار تغيير اسم الرتبة",
        role_color_label="اسم خيار تغيير لون الرتبة",
        role_color_emoji="إيموجي خيار تغيير لون الرتبة",
    )
    @app_commands.choices(
        embed_color=[app_commands.Choice(name=name, value=value) for name, value in EMBED_COLOR_CHOICES],
        role_hoist=[
            app_commands.Choice(name="تظهر بشكل منفصل", value=1),
            app_commands.Choice(name="لا تظهر بشكل منفصل", value=0),
        ],
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_vip(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        role_1: discord.Role,
        role_2: discord.Role,
        embed_title: str | None = None,
        embed_description: str | None = None,
        embed_image: str | None = None,
        embed_thumbnail: str | None = None,
        embed_color: app_commands.Choice[int] | None = None,
        role_hoist: app_commands.Choice[int] | None = None,
        menu_placeholder: str | None = None,
        nickname_label: str | None = None,
        nickname_emoji: str | None = None,
        create_role_label: str | None = None,
        create_role_emoji: str | None = None,
        role_name_label: str | None = None,
        role_name_emoji: str | None = None,
        role_color_label: str | None = None,
        role_color_emoji: str | None = None,
    ):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("❌ هذا الأمر داخل السيرفر فقط.", ephemeral=True)
            return
        if role_1.id == role_2.id:
            await interaction.response.send_message("❌ لازم تختار رتبتين مختلفتين.", ephemeral=True)
            return
        me = guild.me
        if not me:
            await interaction.response.send_message("❌ لم أستطع العثور على البوت.", ephemeral=True)
            return
        if not me.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ البوت يحتاج Manage Roles.", ephemeral=True)
            return
        if not me.guild_permissions.manage_nicknames:
            await interaction.response.send_message("❌ البوت يحتاج Manage Nicknames.", ephemeral=True)
            return
        base_role = guild.get_role(VIP_BASE_ROLE_ID)
        if not base_role:
            await interaction.response.send_message(
                f"❌ الرتبة الأساسية `{VIP_BASE_ROLE_ID}` غير موجودة في السيرفر.", ephemeral=True
            )
            return
        if me.top_role <= base_role:
            await interaction.response.send_message(
                "❌ رتبة البوت لازم تكون أعلى من الرتبة الأساسية المحددة.", ephemeral=True
            )
            return
        old_config = await get_config(guild.id)
        if old_config and old_config.get("channel_id") and old_config.get("message_id"):
            old_channel = guild.get_channel(int(old_config["channel_id"]))
            if old_channel:
                try:
                    old_message = await old_channel.fetch_message(int(old_config["message_id"]))
                    await old_message.delete()
                except Exception:
                    pass
        config = {
            "channel_id": channel.id,
            "message_id": 0,
            "role_1_id": role_1.id,
            "role_2_id": role_2.id,
            "base_role_id": VIP_BASE_ROLE_ID,
            "role_hoist": bool(role_hoist.value) if role_hoist else False,
            "embed_title": text_or_default(embed_title, DEFAULT_TITLE, 256),
            "embed_description": text_or_default(embed_description, DEFAULT_DESCRIPTION, 4000),
            "embed_image": (embed_image or "").strip(),
            "embed_thumbnail": (embed_thumbnail or "").strip(),
            "embed_color": int(embed_color.value) if embed_color else DEFAULT_EMBED_COLOR,
            "menu_placeholder": text_or_default(menu_placeholder, "اختر الميزة التي تريد استخدامها", 150),
            "nickname_label": text_or_default(nickname_label, "تغيير اسم العضو"),
            "nickname_emoji": emoji_or_default(nickname_emoji, "✏️"),
            "create_role_label": text_or_default(create_role_label, "إنشاء رتبة خاصة"),
            "create_role_emoji": emoji_or_default(create_role_emoji, "🎨"),
            "role_name_label": text_or_default(role_name_label, "تغيير اسم الرتبة"),
            "role_name_emoji": emoji_or_default(role_name_emoji, "🏷️"),
            "role_color_label": text_or_default(role_color_label, "تغيير لون الرتبة"),
            "role_color_emoji": emoji_or_default(role_color_emoji, "🌈"),
            "enabled": True,
        }
        embed = build_vip_embed(guild, config)
        try:
            message = await channel.send(embed=embed, view=VIPView(self, config))
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"❌ تعذر إرسال الـEmbed. تأكد من صحة روابط الصور.\n`{e}`",
                ephemeral=True,
            )
            return
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ البوت لا يستطيع إرسال الرسالة في الروم المحدد.", ephemeral=True
            )
            return
        config["message_id"] = message.id
        await save_config(guild.id, config)
        await interaction.response.send_message(
            "✅ تم إعداد نظام VIP بالقائمة الجديدة وحفظ الإعدادات.", ephemeral=True
        )
    @edit_group.command(name="vip", description="تعديل نظام VIP الحالي")
    @app_commands.describe(
        channel="روم رسالة VIP الجديدة - اتركه فارغاً للإبقاء على الحالي",
        role_1="الرتبة الأولى - اتركها فارغة للإبقاء على الحالية",
        role_2="الرتبة الثانية - اتركها فارغة للإبقاء على الحالية",
        embed_title="عنوان الـEmbed - اتركه فارغاً للإبقاء على الحالي",
        embed_description="رسالة الـEmbed - اتركها فارغة للإبقاء على الحالية",
        embed_image="رابط الصورة الكبيرة - اتركه فارغاً للإبقاء على الحالي",
        embed_thumbnail="رابط الـThumbnail - اتركه فارغاً للإبقاء على الحالي",
        embed_color="لون الـEmbed",
        role_hoist="هل تظهر رتبة العضو بشكل منفصل؟",
        menu_placeholder="النص أعلى قائمة المميزات",
        nickname_label="اسم خيار تغيير اسم العضو",
        nickname_emoji="إيموجي خيار تغيير اسم العضو",
        create_role_label="اسم خيار إنشاء الرتبة",
        create_role_emoji="إيموجي خيار إنشاء الرتبة",
        role_name_label="اسم خيار تغيير اسم الرتبة",
        role_name_emoji="إيموجي خيار تغيير اسم الرتبة",
        role_color_label="اسم خيار تغيير لون الرتبة",
        role_color_emoji="إيموجي خيار تغيير لون الرتبة",
    )
    @app_commands.choices(
        embed_color=[app_commands.Choice(name=name, value=value) for name, value in EMBED_COLOR_CHOICES],
        role_hoist=[
            app_commands.Choice(name="تظهر بشكل منفصل", value=1),
            app_commands.Choice(name="لا تظهر بشكل منفصل", value=0),
        ],
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def edit_vip(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
        role_1: discord.Role | None = None,
        role_2: discord.Role | None = None,
        embed_title: str | None = None,
        embed_description: str | None = None,
        embed_image: str | None = None,
        embed_thumbnail: str | None = None,
        embed_color: app_commands.Choice[int] | None = None,
        role_hoist: app_commands.Choice[int] | None = None,
        menu_placeholder: str | None = None,
        nickname_label: str | None = None,
        nickname_emoji: str | None = None,
        create_role_label: str | None = None,
        create_role_emoji: str | None = None,
        role_name_label: str | None = None,
        role_name_emoji: str | None = None,
        role_color_label: str | None = None,
        role_color_emoji: str | None = None,
    ):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("❌ هذا الأمر داخل السيرفر فقط.", ephemeral=True)
            return
        config = await get_config(guild.id)
        if not config or not config.get("enabled"):
            await interaction.response.send_message("❌ نظام VIP غير مفعل. استخدم `/set vip` أولاً.", ephemeral=True)
            return
        current_role_1 = guild.get_role(int(config.get("role_1_id"))) if config.get("role_1_id") else None
        current_role_2 = guild.get_role(int(config.get("role_2_id"))) if config.get("role_2_id") else None
        new_role_1 = role_1 or current_role_1
        new_role_2 = role_2 or current_role_2
        if not new_role_1 or not new_role_2:
            await interaction.response.send_message("❌ لا يمكن تحديد رتبات VIP الحالية. استخدم `/set vip` مرة أخرى.", ephemeral=True)
            return
        if new_role_1.id == new_role_2.id:
            await interaction.response.send_message("❌ لازم تختار رتبتين مختلفتين.", ephemeral=True)
            return
        me = guild.me
        if not me:
            await interaction.response.send_message("❌ لم أستطع العثور على البوت.", ephemeral=True)
            return
        if not me.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ البوت يحتاج Manage Roles.", ephemeral=True)
            return
        if not me.guild_permissions.manage_nicknames:
            await interaction.response.send_message("❌ البوت يحتاج Manage Nicknames.", ephemeral=True)
            return
        base_role = guild.get_role(VIP_BASE_ROLE_ID)
        if not base_role or me.top_role <= base_role:
            await interaction.response.send_message("❌ رتبة البوت يجب أن تكون أعلى من الرتبة الأساسية المحددة.", ephemeral=True)
            return
        old_channel = guild.get_channel(int(config["channel_id"])) if config.get("channel_id") else None
        old_message = None
        if old_channel and config.get("message_id"):
            try:
                old_message = await old_channel.fetch_message(int(config["message_id"]))
            except Exception:
                old_message = None
        # None = keep current. An explicitly supplied description is always used as-is; no default template is substituted.
        config.update({
            "channel_id": (channel or old_channel).id if (channel or old_channel) else config.get("channel_id"),
            "role_1_id": new_role_1.id,
            "role_2_id": new_role_2.id,
            "role_hoist": bool(role_hoist.value) if role_hoist else bool(config.get("role_hoist", False)),
            "embed_title": embed_title.strip() if embed_title is not None and embed_title.strip() else config.get("embed_title") or DEFAULT_TITLE,
            "embed_description": embed_description.strip() if embed_description is not None and embed_description.strip() else config.get("embed_description") or DEFAULT_DESCRIPTION,
            "embed_image": embed_image.strip() if embed_image is not None and embed_image.strip() else config.get("embed_image", ""),
            "embed_thumbnail": embed_thumbnail.strip() if embed_thumbnail is not None and embed_thumbnail.strip() else config.get("embed_thumbnail", ""),
            "embed_color": int(embed_color.value) if embed_color else int(config.get("embed_color", DEFAULT_EMBED_COLOR)),
            "menu_placeholder": menu_placeholder.strip() if menu_placeholder is not None and menu_placeholder.strip() else config.get("menu_placeholder") or "اختر الميزة التي تريد استخدامها",
            "nickname_label": nickname_label.strip() if nickname_label is not None and nickname_label.strip() else config.get("nickname_label") or "تغيير اسم العضو",
            "nickname_emoji": emoji_or_default(nickname_emoji, config.get("nickname_emoji") or "✏️"),
            "create_role_label": create_role_label.strip() if create_role_label is not None and create_role_label.strip() else config.get("create_role_label") or "إنشاء رتبة خاصة",
            "create_role_emoji": emoji_or_default(create_role_emoji, config.get("create_role_emoji") or "🎨"),
            "role_name_label": role_name_label.strip() if role_name_label is not None and role_name_label.strip() else config.get("role_name_label") or "تغيير اسم الرتبة",
            "role_name_emoji": emoji_or_default(role_name_emoji, config.get("role_name_emoji") or "🏷️"),
            "role_color_label": role_color_label.strip() if role_color_label is not None and role_color_label.strip() else config.get("role_color_label") or "تغيير لون الرتبة",
            "role_color_emoji": emoji_or_default(role_color_emoji, config.get("role_color_emoji") or "🌈"),
            "enabled": True,
        })
        target_channel = channel or old_channel
        if not target_channel:
            await interaction.response.send_message("❌ لم أستطع العثور على روم رسالة VIP الحالية.", ephemeral=True)
            return
        embed = build_vip_embed(guild, config)
        try:
            if old_message and target_channel.id == old_channel.id:
                await old_message.edit(embed=embed, view=VIPView(self, config))
                message_id = old_message.id
            else:
                new_message = await target_channel.send(embed=embed, view=VIPView(self, config))
                message_id = new_message.id
                if old_message:
                    try:
                        await old_message.delete()
                    except Exception:
                        pass
            config["message_id"] = message_id
            await save_config(guild.id, config)
            await interaction.response.send_message("✅ تم تعديل إعدادات VIP وتحديث الـEmbed مباشرةً.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ البوت لا يملك الصلاحيات الكافية لتعديل/إرسال رسالة VIP.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"❌ تعذر تحديث الـEmbed. تأكد من صحة روابط الصور.\n`{e}`", ephemeral=True)

    async def apply_role_color(self, interaction, member, role_name, color, existing_role, create_new):
        guild = interaction.guild
        if not guild:
            return
        config = await get_config(guild.id)
        if not config or not has_vip_access(member, config):
            await interaction.response.edit_message(content=NO_VIP_MESSAGE, view=None)
            return
        me = guild.me
        if not me or not me.guild_permissions.manage_roles:
            await interaction.response.edit_message(content="❌ البوت لا يملك Manage Roles.", view=None)
            return
        base_role = guild.get_role(int(config.get("base_role_id", VIP_BASE_ROLE_ID)))
        if not base_role:
            await interaction.response.edit_message(content="❌ الرتبة الأساسية غير موجودة.", view=None)
            return
        if me.top_role <= base_role:
            await interaction.response.edit_message(
                content="❌ رتبة البوت يجب أن تكون أعلى من الرتبة الأساسية.", view=None
            )
            return
        try:
            if create_new:
                if existing_role:
                    await interaction.response.edit_message(content="❌ لديك رتبة خاصة بالفعل.", view=None)
                    return
                new_role = await guild.create_role(
                    name=role_name,
                    color=discord.Color(color),
                    hoist=bool(config.get("role_hoist", False)),
                    reason="VIP - إنشاء رتبة خاصة",
                )
                target_position = base_role.position + 1
                if target_position < me.top_role.position:
                    await new_role.edit(position=target_position, reason="VIP - ترتيب الرتبة الخاصة")
                await member.add_roles(new_role, reason="VIP - إضافة الرتبة الخاصة")
                await save_member_vip(guild.id, member.id, new_role.id, role_name, color)
                await interaction.response.edit_message(
                    content=f"✅ تم إنشاء رتبتك **{role_name}** باللون `#{color:06X}`.",
                    view=None,
                )
                return
            if not existing_role:
                await interaction.response.edit_message(content="❌ لا توجد رتبة خاصة لتغيير لونها.", view=None)
                return
            if existing_role >= me.top_role:
                await interaction.response.edit_message(
                    content="❌ لا أستطيع تعديل هذه الرتبة لأنها أعلى من رتبة البوت.", view=None
                )
                return
            await existing_role.edit(
                color=discord.Color(color),
                hoist=bool(config.get("role_hoist", False)),
                reason="VIP - تغيير لون الرتبة الخاصة",
            )
            await save_member_vip(guild.id, member.id, existing_role.id, existing_role.name, color)
            await interaction.response.edit_message(
                content=f"✅ تم تغيير لون رتبتك إلى `#{color:06X}`.", view=None
            )
        except discord.Forbidden:
            await interaction.response.edit_message(
                content="❌ البوت لا يملك الصلاحيات الكافية لتعديل الرتبة.", view=None
            )
        except Exception as e:
            await interaction.response.edit_message(content=f"❌ حصل خطأ: `{e}`", view=None)
    @tasks.loop(seconds=CHECK_INTERVAL)
    async def vip_checker(self):
        for guild in self.bot.guilds:
            try:
                config = await get_config(guild.id)
                if not config or not config.get("enabled"):
                    continue
                role_1 = guild.get_role(int(config["role_1_id"])) if config.get("role_1_id") else None
                role_2 = guild.get_role(int(config["role_2_id"])) if config.get("role_2_id") else None
                cursor = vip_members.find({"guild_id": guild.id})
                async for data in cursor:
                    user_id = int(data["user_id"])
                    role_id = int(data["role_id"])
                    custom_role = guild.get_role(role_id)
                    if not custom_role:
                        await delete_member_vip(guild.id, user_id)
                        continue
                    member = guild.get_member(user_id)
                    if not member:
                        try:
                            await custom_role.delete(reason="VIP - العضو غادر السيرفر")
                        except Exception:
                            pass
                        await delete_member_vip(guild.id, user_id)
                        continue
                    has_access = (
                        (role_1 is not None and role_1 in member.roles)
                        or (role_2 is not None and role_2 in member.roles)
                    )
                    if not has_access:
                        try:
                            await custom_role.delete(reason="VIP - فقد رتبة VIP")
                        except Exception:
                            pass
                        await delete_member_vip(guild.id, user_id)
            except Exception as e:
                print(f"[VIP] خطأ أثناء الفحص في {guild.name}: {e}")
    @vip_checker.before_loop
    async def before_vip_checker(self):
        await self.bot.wait_until_ready()
    async def cog_load(self):
        self.bot.add_view(VIPView(self))
        if not self.vip_checker.is_running():
            self.vip_checker.start()
async def setup(bot):
    await bot.add_cog(VIPCog(bot))
