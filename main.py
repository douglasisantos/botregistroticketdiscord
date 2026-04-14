import discord
import datetime
import os
import re
import sqlite3
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
    1463187013271556162,
    1493398454150627511
]

# ================= BOT =================

intents = discord.Intents.default()
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

def is_staff(member: discord.Member):
    return any(role.id in STAFF_ROLES_IDS for role in member.roles)

# ================= BANCO =================

def conectar():
    return sqlite3.connect("farm.db")

def criar_tabela():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS farm (
        user_id TEXT PRIMARY KEY,
        nome TEXT,
        alvejante INTEGER,
        papel INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS controle (
        id INTEGER PRIMARY KEY,
        ultimo_reset TEXT
    )
    """)

    conn.commit()
    conn.close()

# ================= FARM =================

def adicionar_farm(user_id, nome, alvejante, papel):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM farm WHERE user_id = ?", (user_id,))
    resultado = cursor.fetchone()

    if resultado:
        cursor.execute("""
        UPDATE farm
        SET alvejante = alvejante + ?, papel = papel + ?
        WHERE user_id = ?
        """, (alvejante, papel, user_id))
    else:
        cursor.execute("""
        INSERT INTO farm (user_id, nome, alvejante, papel)
        VALUES (?, ?, ?, ?)
        """, (user_id, nome, alvejante, papel))

    conn.commit()
    conn.close()

def pegar_ranking():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT nome, alvejante, papel,
    (alvejante + papel) as total
    FROM farm
    ORDER BY total DESC
    LIMIT 10
    """)

    dados = cursor.fetchall()
    conn.close()
    return dados

def pegar_usuario(user_id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT alvejante, papel FROM farm WHERE user_id = ?", (user_id,))
    resultado = cursor.fetchone()

    conn.close()
    return resultado

def resetar_farm():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM farm")

    conn.commit()
    conn.close()

# ================= CONTROLE RESET =================

def precisa_resetar():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT ultimo_reset FROM controle WHERE id = 1")
    resultado = cursor.fetchone()

    agora = datetime.datetime.now()

    if agora.weekday() != 5:
        conn.close()
        return False

    if agora.hour < 2:
        conn.close()
        return False

    if not resultado:
        conn.close()
        return True

    ultimo = datetime.datetime.fromisoformat(resultado[0])

    if ultimo.date() == agora.date():
        conn.close()
        return False

    conn.close()
    return True

def salvar_reset():
    conn = conectar()
    cursor = conn.cursor()

    agora = datetime.datetime.now().isoformat()

    cursor.execute("""
    INSERT INTO controle (id, ultimo_reset)
    VALUES (1, ?)
    ON CONFLICT(id) DO UPDATE SET ultimo_reset = excluded.ultimo_reset
    """, (agora,))

    conn.commit()
    conn.close()

# ================= FARM COMMANDS =================

class Farm(app_commands.Group):
    def __init__(self):
        super().__init__(name="farm", description="Sistema de farm da fac")

    @app_commands.command(name="adicionar", description="Adicionar farm")
    async def adicionar(self, interaction: discord.Interaction, alvejante: int, papel: int):

        adicionar_farm(
            str(interaction.user.id),
            interaction.user.display_name,
            alvejante,
            papel
        )

        dados = pegar_usuario(str(interaction.user.id))

        await interaction.response.send_message(
            f"✅ Farm registrado!\n\n"
            f"🔧 Alvejante: +{alvejante}\n"
            f"🧪 Papel: +{papel}\n\n"
            f"📊 Total:\n"
            f"🔧 {dados[0]}\n"
            f"🧪 {dados[1]}"
        )

    @app_commands.command(name="ranking", description="Ranking de farm")
    async def ranking(self, interaction: discord.Interaction):

        dados = pegar_ranking()

        if not dados:
            return await interaction.response.send_message("❌ Nenhum dado ainda.")

        embed = discord.Embed(
            title="🏆 Ranking de Farm",
            color=discord.Color.gold()
        )

        for i, (nome, alvejante, papel, total) in enumerate(dados, start=1):
            embed.add_field(
                name=f"{i}º - {nome}",
                value=f"🔧 {alvejante} | 🧪 {papel}",
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ver", description="Ver farm de um membro")
    async def ver(self, interaction: discord.Interaction, membro: discord.Member):

        resultado = pegar_usuario(str(membro.id))

        if not resultado:
            return await interaction.response.send_message("❌ Esse usuário não tem farm.")

        await interaction.response.send_message(
            f"📊 Farm de {membro.mention}:\n\n"
            f"🔧 {resultado[0]}\n"
            f"🧪 {resultado[1]}"
        )

# ================= RESET =================

@tasks.loop(minutes=10)
async def reset_semanal():
    if precisa_resetar():
        resetar_farm()
        salvar_reset()
        print("🧹 Reset automático realizado!")

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

        nome_limpo = re.sub(r'[^a-z0-9-]', '-', user.display_name.lower())

        canal = await guild.create_text_channel(
            name=nome_limpo[:20],
            category=categoria,
            overwrites=overwrites
        )

        await canal.send(
            f"👋 {user.mention}\n\n"
            f"💰 Use:\n"
            f"`/farm adicionar Alvejante:100 Papel:100`\n\n"
            f"📅 Pagamento semanal (sábado 02:00)"
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
    criar_tabela()

    bot.add_view(TicketView())

    guild = discord.Object(id=GUILD_ID)

    bot.tree.clear_commands(guild=guild)
    bot.tree.add_command(Farm(), guild=guild)

    await bot.tree.sync(guild=guild)

    reset_semanal.start()

    print(f"🤖 Online como {bot.user}")

bot.run(TOKEN)