import discord
from discord.ext import commands
from discord import ui, Interaction, ButtonStyle
from github import Github
import json
import secrets
import string
from datetime import datetime
import os

# ============================================================
# 🔥 CONFIGURACIÓN - USA VARIABLES DE ENTORNO
# ============================================================
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
BUYER_ROLE_ID = int(os.getenv("BUYER_ROLE_ID", 0))
CANAL_PANEL_ID = int(os.getenv("CANAL_PANEL_ID", 0))
WEB_BASE_URL = os.getenv("WEB_BASE_URL", "https://stickpanel.up.railway.app")
# ============================================================

if not GITHUB_TOKEN or not DISCORD_TOKEN:
    print("❌ Error: Faltan variables de entorno. Asegúrate de configurar GITHUB_TOKEN y DISCORD_TOKEN.")
    exit(1)

g = Github(GITHUB_TOKEN)
repo = g.get_repo("rblx-api/stick-bot-sistema-de-keys")

def leer_data():
    try:
        contenido = repo.get_contents("keys.json")
        data = json.loads(contenido.decoded_content)
        if "script_template" not in data:
            data["script_template"] = "-- 💜 Script personalizado de Stick\nprint('¡Hola! Este es tu script personalizado.')"
        if "keys" not in data:
            data["keys"] = {}
        return data
    except Exception as e:
        print(f"⚠️ Error al leer keys.json: {e}")
        return {"script_template": "-- 💜 Script personalizado de Stick\nprint('¡Hola Mundo!')", "keys": {}}

def guardar_data(data):
    try:
        contenido = repo.get_contents("keys.json")
        repo.update_file(contenido.path, "Actualizando data", json.dumps(data, indent=2), contenido.sha)
        print("✅ Datos guardados en GitHub")
    except Exception as e:
        print(f"⚠️ No se encontró keys.json, creándolo: {e}")
        repo.create_file("keys.json", "Creando data", json.dumps(data, indent=2))
        print("✅ keys.json creado")

def generar_clave(script_name):
    alphabet = string.ascii_uppercase + string.digits
    key = ''.join(secrets.choice(alphabet) for _ in range(16))
    key = '-'.join(key[i:i+4] for i in range(0, 16, 4))
    data = leer_data()
    data["keys"][key] = {
        "script": script_name,
        "activa": True,
        "redeemed_by": None,
        "user_code": None,
        "hwid": None,
        "roblox_uid": None,
        "roblox_name": None,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    guardar_data(data)
    return key

def get_user_info(user_id_str):
    data = leer_data()
    for key, info in data.get("keys", {}).items():
        if info.get("redeemed_by") == user_id_str and not info.get("activa", True):
            return info.get("user_code"), key
    return None, None

# ============================================================
# 🖥️ MODAL PARA CANJEAR CLAVE
# ============================================================
class RedeemModal(ui.Modal, title='🔑 Canjear Clave'):
    key_input = ui.TextInput(
        label='Escribe tu clave aquí',
        placeholder='Ej: ABCD-EFGH-IJKL-MNOP',
        min_length=19,
        max_length=19,
        required=True
    )
    def __init__(self, user_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id = user_id

    async def on_submit(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        key = self.key_input.value
        data = leer_data()
        keys = data.get("keys", {})
        
        if key not in keys:
            await interaction.followup.send("❌ Clave no encontrada.", ephemeral=True)
            return
        
        info = keys[key]
        if not info.get("activa", False):
            await interaction.followup.send("❌ Clave ya usada o inactiva.", ephemeral=True)
            return
        
        user_code = secrets.token_hex(16)
        info["activa"] = False
        info["redeemed_by"] = str(self.user_id)
        info["user_code"] = user_code
        info["hwid"] = None
        guardar_data(data)
        
        await interaction.followup.send(
            f"✅ Clave `{key}` canjeada con éxito.\n"
            f"🔑 Tu código único: `{user_code}`\n"
            f"Ahora usa el botón **Generate Script** para obtener tu loadstring.",
            ephemeral=True
        )

# ============================================================
# 🎛️ PANEL PÚBLICO
# ============================================================
class PublicStickPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label='🔑 Redeem Key', style=ButtonStyle.success)
    async def redeem_button(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(RedeemModal(interaction.user.id))

    @ui.button(label='📜 Generate Script', style=ButtonStyle.primary)
    async def generate_button(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        user_code, key = get_user_info(str(interaction.user.id))
        if not user_code:
            await interaction.followup.send(
                "❌ No has canjeado una clave válida. Usa **Redeem Key** primero.",
                ephemeral=True
            )
            return
        
        script_block = (
            f'script_key = "{key}"\n'
            f'loadstring(game:HttpGet("{WEB_BASE_URL}/raw/{user_code}"))()'
        )
        await interaction.followup.send(
            f"✅ **Script listo para ejecutar:**\n```lua\n{script_block}\n```\n"
            "📌 Copia y pega esto en tu ejecutor de Roblox.",
            ephemeral=True
        )

    @ui.button(label='🔄 Reset Cuenta', style=ButtonStyle.secondary)
    async def reset_hwid_button(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        user_id_str = str(interaction.user.id)
        data = leer_data()
        for key, info in data.get("keys", {}).items():
            if info.get("redeemed_by") == user_id_str:
                info["hwid"] = None
                info["roblox_uid"] = None
                info["roblox_name"] = None
                guardar_data(data)
                await interaction.followup.send(
                    "🔄 Cuenta de Roblox desvinculada. Ya puedes ejecutar el script en otra cuenta.",
                    ephemeral=True
                )
                return
        await interaction.followup.send("❌ No tienes clave activa.", ephemeral=True)

    @ui.button(label='🎖️ Get Buyer Role', style=ButtonStyle.success)
    async def buyer_role_button(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        user_id_str = str(interaction.user.id)
        data = leer_data()
        has_key = any(info.get("redeemed_by") == user_id_str and not info.get("activa", True)
                      for info in data.get("keys", {}).values())
        if not has_key:
            await interaction.followup.send("❌ Canjea una clave primero.", ephemeral=True)
            return
        role = interaction.guild.get_role(BUYER_ROLE_ID)
        if not role:
            await interaction.followup.send("⚠️ Rol no configurado. Revisa el ID.", ephemeral=True)
            return
        member = interaction.guild.get_member(interaction.user.id)
        if role in member.roles:
            await interaction.followup.send("✅ Ya tienes el rol.", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.followup.send(f"🎉 ¡Rol {role.name} asignado!", ephemeral=True)

# ============================================================
# 🤖 BOT DE DISCORD
# ============================================================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'✅ Bot conectado como {bot.user}')
    channel = bot.get_channel(CANAL_PANEL_ID)
    if channel:
        embed = discord.Embed(
            title="📟 Stick Panel",
            description="Interactúa con los botones para gestionar tu licencia.",
            color=0x9b59b6
        )
        embed.set_footer(text="Sistema de Keys v2.0")
        await channel.send(embed=embed, view=PublicStickPanelView())
        print(f"✅ Panel enviado al canal {channel.name}")
    else:
        print(f"❌ ERROR: No encontré el canal con ID {CANAL_PANEL_ID}")

@bot.command()
@commands.has_permissions(administrator=True)
async def generar(ctx, script: str):
    clave = generar_clave(script)
    await ctx.send(f"🔑 Clave generada para `{script}`:\n`{clave}`")

@bot.command()
@commands.has_permissions(administrator=True)
async def listar_claves(ctx):
    data = leer_data()
    keys = data.get("keys", {})
    if not keys:
        await ctx.send("📭 No hay claves guardadas.")
        return
    mensaje = "📋 **Lista de claves:**\n"
    for k, v in list(keys.items())[:10]:
        estado = "✅ Activa" if v.get("activa") else "❌ Usada"
        usuario = v.get("redeemed_by") or "Nadie"
        codigo = v.get("user_code") or "Sin código"
        mensaje += f"- `{k}` → Script: `{v.get('script')}` | {estado} | Usuario: {usuario} | Código: {codigo}\n"
    await ctx.send(mensaje)

bot.run(DISCORD_TOKEN)