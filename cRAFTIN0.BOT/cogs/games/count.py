import random
import asyncio
import os
import discord
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# تحميل المتغيرات والاتصال بقاعدة بيانات MongoDB
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

client = AsyncIOMotorClient(MONGO_URI)
db = client["CRAFTINO_DB"]
games_collection = db["active_guess_games"]


class GuessGameView(discord.ui.View):

    def __init__(self, cog, channel_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.channel_id = channel_id
        self.players = {}  # {user_id: discord.Member}

    @discord.ui.button(
        label="دخول اللعبة",
        style=discord.ButtonStyle.green,
        custom_id="join_guess_game",
    )
    async def join_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id in self.players:
            await interaction.response.send_message(
                "أنت منضم بالفعل لهذه اللعبة!", ephemeral=True
            )
            return

        if len(self.players) >= 100:
            await interaction.response.send_message(
                "عذراً، لقد وصل عدد اللاعبين للحد الأقصى (100 عضو).", ephemeral=True
            )
            return

        self.players[interaction.user.id] = interaction.user
        embed = interaction.message.embeds[0]

        players_list_str = (
            "\n".join([f"• {p.mention}" for p in self.players.values()])
            or "لا يوجد"
        )
        if len(players_list_str) > 1024:
            players_list_str = players_list_str[:1020] + "..."

        for index, field in enumerate(embed.fields):
            if "عدد اللاعبين" in field.name:
                embed.set_field_at(
                    index,
                    name="📊 عدد اللاعبين المنضمين",
                    value=(
                        f"العدد: {len(self.players)} /"
                        f" 100\n**اللاعبون:**\n{players_list_str}"
                    ),
                    inline=False,
                )

        await interaction.response.edit_message(embed=embed)
        await interaction.followup.send(
            f"تم انضمامك بنجاح يا {interaction.user.mention}!", ephemeral=True
        )

    @discord.ui.button(
        label="خروج",
        style=discord.ButtonStyle.red,
        custom_id="leave_guess_game",
    )
    async def leave_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id not in self.players:
            await interaction.response.send_message(
                "أنت لست منضمًا أساسًا!", ephemeral=True
            )
            return

        del self.players[interaction.user.id]
        embed = interaction.message.embeds[0]

        players_list_str = (
            "\n".join([f"• {p.mention}" for p in self.players.values()])
            or "لا يوجد"
        )
        if len(players_list_str) > 1024:
            players_list_str = players_list_str[:1020] + "..."

        for index, field in enumerate(embed.fields):
            if "عدد اللاعبين" in field.name:
                embed.set_field_at(
                    index,
                    name="📊 عدد اللاعبين المنضمين",
                    value=(
                        f"العدد: {len(self.players)} /"
                        f" 100\n**اللاعبون:**\n{players_list_str}"
                    ),
                    inline=False,
                )

        await interaction.response.edit_message(embed=embed)
        await interaction.followup.send("تم إخراجك من اللعبة.", ephemeral=True)


class GuessGame(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.game_tasks = {}

    async def is_game_active(self, channel_id: int) -> bool:
        data = await games_collection.find_one({"_id": str(channel_id)})
        return data is not None

    async def set_game_active(self, channel_id: int, active: bool):
        if active:
            await games_collection.update_one(
                {"_id": str(channel_id)},
                {"$set": {"active": True}},
                upsert=True
            )
        else:
            await games_collection.deleteOne({"_id": str(channel_id)}) # type: ignore

    @commands.command(name="خمن")
    async def start_game(self, ctx):
        if await self.is_game_active(ctx.channel.id):
            await ctx.send(
                "هناك لعبة قائمة بالفعل في هذه الروم، انتظر حتى تنتهي.", delete_after=5
            )
            return

        await self.set_game_active(ctx.channel.id, True)
        self.game_tasks[ctx.channel.id] = asyncio.current_task()

        try:
            guild_icon = ctx.guild.icon.url if ctx.guild.icon else None

            embed = discord.Embed(
                title="🎮 لعبة التخمين الكبرى!",
                description=(
                    "اضغط على زر **دخول اللعبة** للمشاركة.\nستبدأ اللعبة تلقائياً بعد"
                    " **30 ثانية**!"
                ),
                color=discord.Color.blue(),
            )
            
            if guild_icon:
                embed.set_thumbnail(url=guild_icon)

            embed.set_image(url="https://i.imgur.com/YOUR_BANNER_LINK_HERE.png")

            embed.add_field(
                name="📊 عدد اللاعبين المنضمين",
                value="العدد: 0 / 100\n**اللاعبون:**\nلا يوجد",
                inline=False,
            )

            view = GuessGameView(self, ctx.channel.id)
            msg = await ctx.send(embed=embed, view=view)

            for i in range(30, 0, -5):
                await asyncio.sleep(5)

            for child in view.children:
                child.disabled = True
            await msg.edit(view=view)

            players_list = list(view.players.values())

            if len(players_list) < 2:
                await ctx.send(
                    "❌ لم يشارك عدد كافٍ من اللاعبين (يجب أن يكون هناك لاعبين على الأقل)."
                )
                await self.set_game_active(ctx.channel.id, False)
                self.game_tasks.pop(ctx.channel.id, None)
                return

            random.shuffle(players_list)
            mid = len(players_list) // 2
            team1 = players_list[:mid]
            team2 = players_list[mid:]

            teams_embed = discord.Embed(
                title="🛡️ تم تقسيم الفرق بنجاح!",
                description="تبدأ اللعبة خلال 5 ثوانٍ...",
                color=discord.Color.gold(),
            )
            if guild_icon:
                teams_embed.set_thumbnail(url=guild_icon)

            teams_embed.add_field(
                name="🔴 فريق رقم 1",
                value="\n".join([f"• {p.mention}" for p in team1]) or "لايوجد",
                inline=False,
            )
            teams_embed.add_field(
                name="🔵 فريق رقم 2",
                value="\n".join([f"• {p.mention}" for p in team2]) or "لايوجد",
                inline=False,
            )
            await ctx.send(embed=teams_embed)
            await asyncio.sleep(5)

            secret_number = random.randint(1, 100)
            min_range = 1
            max_range = 100
            game_active = True
            current_team_turn = 1

            while game_active:
                if not team1 and not team2:
                    await ctx.send("❌ انتهت اللعبة لعدم وجود أي لاعبين متبقين في الفريقين!")
                    game_active = False
                    break
                elif not team1:
                    await ctx.send(
                        "🏆 انتهت اللعبة! تم إقصاء جميع لاعبي الفريق الأول، والفوز من"
                        " نصيب **فريق رقم 2 🔵**!"
                    )
                    game_active = False
                    break
                elif not team2:
                    await ctx.send(
                        "🏆 انتهت اللعبة! تم إقصاء جميع لاعبي الفريق الثاني، والفوز من"
                        " نصيب **فريق رقم 1 🔴**!"
                    )
                    game_active = False
                    break

                await ctx.send("⏳ جاري اختيار شخص عشوائي من الفريق للدور القادم...")
                await asyncio.sleep(4)

                if current_team_turn == 1:
                    if not team1:
                        current_team_turn = 2
                        continue
                    current_player = random.choice(team1)
                    team_num = 1
                else:
                    if not team2:
                        current_team_turn = 1
                        continue
                    current_player = random.choice(team2)
                    team_num = 2

                prompt_msg = await ctx.send(
                    f"🎯 دور اللاعب {current_player.mention} (أنت في **فريق {team_num}**).\nخمن الرقم الصحيح من **{min_range} إلى {max_range}** أمامك **15 ثانية** للرد!"
                )

                def check(m):
                    if m.channel == ctx.channel and m.author != current_player:
                        if m.content.isdigit():
                            asyncio.create_task(m.delete())
                        return False
                    return (
                        m.author == current_player
                        and m.channel == ctx.channel
                        and m.content.isdigit()
                    )

                try:
                    guess_msg = await self.bot.wait_for(
                        "message", timeout=15.0, check=check
                    )
                    guess = int(guess_msg.content)

                    if guess == secret_number:
                        winning_team_name = (
                            "فريق رقم 1 🔴" if team_num == 1 else "فريق رقم 2 🔵"
                        )
                        winning_team_members = team1 if team_num == 1 else team2
                        members_mentions = (
                            ", ".join([p.mention for p in winning_team_members])
                            or "لايوجد"
                        )

                        win_embed = discord.Embed(
                            title="🎉 مبروك الفوز! 🏆",
                            description=(
                                f"كفووو! لقد تمكن اللاعب {current_player.mention} من تخمين"
                                f" الرقم الصحيح **{secret_number}** بنجاح!\n\n🏆 الفوز من"
                                f" نصيب: **{winning_team_name}**"
                            ),
                            color=discord.Color.green(),
                        )
                        win_embed.set_thumbnail(url="https://i.imgur.com/380698z.png")
                        win_embed.add_field(
                            name="👥 أعضاء الفريق الفائز:",
                            value=members_mentions,
                            inline=False,
                        )

                        await ctx.send(embed=win_embed)
                        game_active = False
                        break

                    elif guess < secret_number:
                        if guess > min_range:
                            min_range = guess
                        await ctx.send(
                            f"❌ خطأ! الرقم الصحيح **أكبر** من `{guess}`.\n📊 النطاق الجديد للتخمين القادم: **{min_range} - {max_range}**"
                        )
                    else:
                        if guess < max_range:
                            max_range = guess
                        await ctx.send(
                            f"❌ خطأ! الرقم الصحيح **أصغر** من `{guess}`.\n📊 النطاق الجديد للتخمين القادم: **{min_range} - {max_range}**"
                        )

                    await asyncio.sleep(4)

                except asyncio.TimeoutError:
                    if current_player in team1:
                        team1.remove(current_player)
                    elif current_player in team2:
                        team2.remove(current_player)

                    await ctx.send(
                        f"⏰ انتهى الوقت يا {current_player.mention} ولم تقم بالتخمين!\n🚨 **تم طردك نهائياً من اللعبة!**"
                    )
                    await asyncio.sleep(4)

                current_team_turn = 2 if current_team_turn == 1 else 1

        except asyncio.CancelledError:
            return
        finally:
            await self.set_game_active(ctx.channel.id, False)
            self.game_tasks.pop(ctx.channel.id, None)

    @commands.command(name="توقيف")
    @commands.has_permissions(administrator=True)
    async def stop_game(self, ctx):
        if not await self.is_game_active(ctx.channel.id):
            await ctx.send("❌ لا توجد لعبة قائمة في هذه الروم حالياً.", delete_after=5)
            return

        task = self.game_tasks.get(ctx.channel.id)
        if task:
            task.cancel()

        await self.set_game_active(ctx.channel.id, False)
        self.game_tasks.pop(ctx.channel.id, None)

        await ctx.send(
            f"🛑 تم إيقاف لعبة التخمين بواسطة المشرف {ctx.author.mention} بنجاح."
        )

    @stop_game.error
    async def stop_game_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(
                "❌ عذراً، هذا الأمر مخصص للمشرفين وأصحاب الصلاحيات العالية فقط!",
                delete_after=5,
            )


async def setup(bot):
    await bot.add_cog(GuessGame(bot))