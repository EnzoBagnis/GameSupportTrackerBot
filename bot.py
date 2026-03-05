import discord
import asyncio
import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

# ── CONFIG ──────────────────────────────────────────
DISCORD_TOKEN  = os.getenv("DISCORD_TOKEN")
API_KEY        = os.getenv("GOOGLE_API_KEY")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 30))
CONFIG_FILE    = "servers_config.json"

# 🧪 SHEETS DE TEST
SPREADSHEET_ID = "1fnzhztyJ07Bfz3EMWqpzP1Q4b1i4KTL0Hm72OCRAtmI"

SHEETS = [
    {"name": "Test", "gid": "0", "colonne": 0},
]
# ────────────────────────────────────────────────────

intents                 = discord.Intents.default()
intents.message_content = True
client                  = discord.Client(intents=intents)
known_games             = {}


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_config(config: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_sheet_name_by_gid(gid: str) -> str | None:
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}?key={API_KEY}"
    response = requests.get(url)
    data = response.json()
    for sheet in data.get("sheets", []):
        if str(sheet["properties"]["sheetId"]) == gid:
            return sheet["properties"]["title"]
    return None

def get_games_from_sheet(sheet_title: str, colonne: int) -> set:
    url = (
        f"https://sheets.googleapis.com/v4/spreadsheets/"
        f"{SPREADSHEET_ID}/values/{requests.utils.quote(sheet_title)}!A:Z?key={API_KEY}"
    )
    response = requests.get(url)
    data = response.json()
    rows = data.get("values", [])
    return {row[colonne] for row in rows[1:] if len(row) > colonne}


@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.strip() == "!setchannel":
        if not message.author.guild_permissions.administrator:
            await message.channel.send("❌ Tu dois être administrateur pour faire ça.")
            return

        config = load_config()
        config[str(message.guild.id)] = str(message.channel.id)
        save_config(config)

        known_games[str(message.guild.id)] = {
            sheet["name"]: get_games_from_sheet(sheet["title"], sheet["colonne"])
            for sheet in SHEETS
        }

        await message.channel.send(
            f"✅ Salon configuré ! Le bot surveille le **Sheets de test**.\n"
            f"Ajoute une ligne dans le Sheets pour tester 🎮"
        )

    if message.content.strip() == "!removechannel":
        if not message.author.guild_permissions.administrator:
            await message.channel.send("❌ Tu dois être administrateur pour faire ça.")
            return

        config = load_config()
        if str(message.guild.id) in config:
            del config[str(message.guild.id)]
            save_config(config)
            known_games.pop(str(message.guild.id), None)
            await message.channel.send("✅ Notifications désactivées.")
        else:
            await message.channel.send("⚠️ Aucun salon configuré.")

    if message.content.strip() == "!status":
        config = load_config()
        guild_id = str(message.guild.id)
        if guild_id in config:
            channel = client.get_channel(int(config[guild_id]))
            total = sum(len(v) for v in known_games.get(guild_id, {}).values())
            await message.channel.send(
                f"✅ Bot actif — notifications dans {channel.mention}\n"
                f"📋 {total} entrées suivies au total."
            )
        else:
            await message.channel.send("⚠️ Aucun salon configuré. Tape `!setchannel`.")


async def check_for_new_games():
    await client.wait_until_ready()

    print("🔍 Résolution des onglets...")
    for sheet in SHEETS:
        title = get_sheet_name_by_gid(sheet["gid"])
        sheet["title"] = title if title else sheet["name"]
        print(f"  ✅ '{sheet['name']}' → '{sheet['title']}'")

    config = load_config()
    for guild_id in config:
        known_games[guild_id] = {
            sheet["name"]: get_games_from_sheet(sheet["title"], sheet["colonne"])
            for sheet in SHEETS
        }
        print(f"✅ Serveur {guild_id} chargé.")

    while not client.is_closed():
        await asyncio.sleep(CHECK_INTERVAL)
        config = load_config()
        try:
            for guild_id, channel_id in config.items():
                channel = client.get_channel(int(channel_id))
                if not channel:
                    continue

                if guild_id not in known_games:
                    known_games[guild_id] = {
                        sheet["name"]: get_games_from_sheet(sheet["title"], sheet["colonne"])
                        for sheet in SHEETS
                    }
                    continue

                for sheet in SHEETS:
                    current = get_games_from_sheet(sheet["title"], sheet["colonne"])
                    new     = current - known_games[guild_id][sheet["name"]]

                    for game in new:
                        print(f"🧪 [{guild_id}] Nouvelle entrée : {game}")
                        await channel.send(
                            f"🧪 **[TEST] Nouvelle entrée détectée !**\n"
                            f"> `{game}`\n"
                            f"@everyone"
                        )

                    known_games[guild_id][sheet["name"]] = current

        except Exception as e:
            print(f"❌ Erreur : {e}")


@client.event
async def on_ready():
    print(f"✅ Bot connecté : {client.user}")
    client.loop.create_task(check_for_new_games())


client.run(DISCORD_TOKEN)