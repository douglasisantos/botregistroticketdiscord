import discord
import json
import datetime
import os
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv
load_dotenv()

# ================= CONFIG =================

TOKEN = os.getenv("DISCORD_TOKEN")

GUILD_ID = 1463187012822765856

CANAL_APROVACAO_ID = 1464055118818443597
CANAL_TICKET_ID = 1463187014785568859

CARGO_VISITANTE = "Visitante"
CARGO_MEMBRO = "🔫 | Membros"

STAFF_ROLES_IDS = [
    1463187013271556167,
    1463187013271556166,
    1463187013271556165,
    1463187013271556164,
    1463187013271556163,
    1463187013271556162
]

ARQUIVO_FARM = "farm.json"

# ================= BOT =================

intents = discord.Intents.default()
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

def is_staff(member: discord.Member):
    return any(role.id in STAFF_ROLES_IDS for role in member.roles)

# ================= FARM =================

def carregar_dados():
    try:
        with open(ARQUIVO_FARM, "r") as f:
            return json.load(f)
    except:
        return {}

def salvar_dados(dados):
    with open(ARQUIVO_FARM, "w") as f:
        json.dump(dados, f, indent=4)

class Farm(app_commands.Group):
    def __init__(self):
        super().__init__(name="farm", description="Sistema de farm da fac")

    @app_commands.command(name="adicionar", description="Adicionar farm")
    async def adicionar(self, interaction: discord.Interaction, ferramenta: int, plastico: int):
        dados = carregar_dados()
        user_id = str(interaction.user.id)

        if user_id not in dados:
            dados[user_id] = {
                "nome": interaction.user.display_name,
                "ferramenta": 0,
                "plastico": 0
            }

        dados[user_id]["ferramenta"] += ferramenta
        dados[user_id]["plastico"] += plastico

        salvar_dados(dados)

        await interaction.response.send_message(
            f"✅ Farm registrado!\n\n"
            f"🔧 Ferramenta: +{ferramenta}\n"
            f"🧪 Plástico: +{plastico}\n\n"
            f"📊 Total:\n"
            f"🔧 {dados[user_id]['ferramenta']}\n"
            f"🧪 {dados[user_id]['plastico']}"
        )

    @app_commands.command(name="ranking", description="Ranking de farm")
    async def ranking(self, interaction: discord.Interaction):
        dados = carregar_dados()

        if not dados:
            return await interaction.response.send_message("❌ Nenhum dado ainda.")

        ranking = sorted(
            dados.items(),
            key=lambda x: x[1]["ferramenta"] + x[1]["plastico"],
            reverse=True
        )

        embed = discord.Embed(
            title="🏆 Ranking de Farm",
            color=discord.Color.gold()
        )

        for i, (user_id, info) in enumerate(ranking[:10], start=1):
            embed.add_field(
                name=f"{i}º - {info['nome']}",
                value=f"🔧 {info['ferramenta']} | 🧪 {info['plastico']}",
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ver", description="Ver farm de um membro")
    async def ver(self, interaction: discord.Interaction, membro: discord.Member):
        dados = carregar_dados()
        user_id = str(membro.id)

        if user_id not in dados:
            return await interaction.response.send_message("❌ Esse usuário não tem farm.")

        await interaction.response.send_message(
            f"📊 Farm de {membro.mention}:\n\n"
            f"🔧 {dados[user_id]['ferramenta']}\n"
            f"🧪 {dados[user_id]['plastico']}"
        )

    @app_commands.command(name="relatorio", description="Relatório geral")
    async def relatorio(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Apenas staff.", ephemeral=True)

        dados = carregar_dados()

        texto = ""
        for info in dados.values():
            texto += f"{info['nome']} | 🔧 {info['ferramenta']} | 🧪 {info['plastico']}\n"

        await interaction.response.send_message(f"📊 Relatório:\n\n{texto}")

# ================= RESET SEMANAL =================

@tasks.loop(hours=1)
async def reset_semanal():
    agora = datetime.datetime.now()

    if agora.weekday() == 4 and agora.hour == 0:  # sexta meia-noite
        salvar_dados({})
        print("🧹 Farm resetado (sexta-feira)")

# ================= REGISTRO =================

class RegistroModal(discord.ui.Modal, title="Registro de Membro"):
    nome = discord.ui.TextInput(label="Nome no jogo", required=True)
    id_jogo = discord.ui.TextInput(label="ID do jogo", required=True)
    telefone = discord.ui.TextInput(label="Telefone", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        canal = interaction.guild.get_channel(CANAL_APROVACAO_ID)

        embed = discord.Embed(title="📋 Novo Registro", color=discord.Color.gold())
        embed.add_field(name="👤 Usuário", value=interaction.user.mention, inline=False)
        embed.add_field(name="🎮 Nome", value=self.nome.value)
        embed.add_field(name="🆔 ID", value=self.id_jogo.value)
        embed.add_field(name="📞 Telefone", value=self.telefone.value)

        await canal.send(
            embed=embed,
            view=AprovacaoView(interaction.user.id, self.nome.value, self.id_jogo.value)
        )

        await interaction.response.send_message("✅ Registro enviado.", ephemeral=True)

class AprovacaoView(discord.ui.View):
    def __init__(self, user_id, nome, id_jogo):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.nome = nome
        self.id_jogo = id_jogo

    @discord.ui.button(label="✅ Aprovar", style=discord.ButtonStyle.green)
    async def aprovar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Apenas staff.", ephemeral=True)

        membro = interaction.guild.get_member(self.user_id)

        await membro.edit(nick=f"{self.nome} | {self.id_jogo}")
        await membro.add_roles(discord.utils.get(interaction.guild.roles, name=CARGO_MEMBRO))
        await membro.remove_roles(discord.utils.get(interaction.guild.roles, name=CARGO_VISITANTE))

        await interaction.response.send_message(f"✅ {membro.mention} aprovado!")

# ================= TICKET =================

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📩 Criar Ticket", style=discord.ButtonStyle.primary, custom_id="ticket_criar")
    async def criar_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        user = interaction.user

        categoria = discord.utils.get(guild.categories, name="Tickets")
        if categoria is None:
            categoria = await guild.create_category("Tickets")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        for role in guild.roles:
            if role.id in STAFF_ROLES_IDS:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        canal = await guild.create_text_channel(
            name=f"{user.display_name}".lower(),
            category=categoria,
            overwrites=overwrites
        )

        # 👇 MENSAGEM AUTOMÁTICA
        await canal.send(
            f"👋 {user.mention}\n\n"
            f"💰 Use:\n"
            f"`/farm adicionar ferramenta:100 plastico:100`\n\n"
            f"📅 Pagamento semanal (sexta-feira)"
        )

        await interaction.followup.send(f"✅ Ticket criado: {canal.mention}", ephemeral=True)

# ================= COMMANDS =================

@bot.tree.command(name="registrar")
async def registrar(interaction: discord.Interaction):
    await interaction.response.send_modal(RegistroModal())

@bot.tree.command(name="setupticket")
async def setupticket(interaction: discord.Interaction):
    canal = interaction.guild.get_channel(CANAL_TICKET_ID)

    embed = discord.Embed(
        title="🎫 Tickets",
        description="Abra um ticket",
        color=discord.Color.blue()
    )

    await canal.send(embed=embed, view=TicketView())
    await interaction.response.send_message("✅ Painel criado", ephemeral=True)

# ================= READY =================

@bot.event
async def on_ready():
    bot.add_view(TicketView())

    guild = discord.Object(id=GUILD_ID)

    bot.tree.clear_commands(guild=guild)
    bot.tree.add_command(Farm(), guild=guild)

    await bot.tree.sync(guild=guild)

    reset_semanal.start()

    print(f"🤖 Online como {bot.user}")

bot.run(TOKEN)