import discord
import asyncio
import requests
import os
import json
import redis
from dotenv import load_dotenv

load_dotenv()

# -- CONFIG --
DISCORD_TOKEN  = os.getenv("DISCORD_TOKEN")
API_KEY        = os.getenv("GOOGLE_API_KEY")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 60))
REDIS_URL      = os.getenv("REDIS_URL")

SPREADSHEET_ID = "1iuzDTOAvdoNe8Ne8i461qGNucg5OuEoF-Ikqs8aUQZw"

SHEETS = [
    {"name": "Playable Worlds", "gid": "58422002",   "colonne": 0},
    {"name": "Core Verified",   "gid": "1675722515", "colonne": 0},
]
# -------------

intents                 = discord.Intents.default()
intents.message_content = True
client                  = discord.Client(intents=intents)
known_games             = {}


# -- Redis --

def get_redis():
    return redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=5)

def wait_for_redis(max_attempts=10):
    for attempt in range(1, max_attempts + 1):
        try:
            r = get_redis()
            r.ping()
            print(f"Redis connecte apres {attempt} tentative(s).")
            return True
        except Exception as e:
            print(f"Redis pas encore pret (tentative {attempt}/{max_attempts}) : {e}")
            import time
            time.sleep(3)
    print("Impossible de se connecter a Redis.")
    return False

def load_config() -> dict:
    try:
        r   = get_redis()
        raw = r.get("servers_config")
        if raw:
            return json.loads(raw)
        else:
            print("Aucune config trouvee dans Redis.")
    except Exception as e:
        print(f"Erreur lecture Redis : {e}")
    return {}

def save_config(config: dict):
    try:
        r = get_redis()
        r.set("servers_config", json.dumps(config))
        print(f"Config sauvegardee dans Redis : {json.dumps(config)}")
    except Exception as e:
        print(f"Erreur sauvegarde Redis : {e}")


# -- Google Sheets --

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

def get_ping(config: dict, guild_id: str) -> str:
    role_id = config.get(guild_id + "_role")
    if role_id:
        return f"<@&{role_id}>"
    return "@everyone"


# -- Commandes Discord --

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.strip() == "!setchannel":
        if not message.author.guild_permissions.administrator:
            await message.channel.send("Tu dois etre administrateur pour faire ca.")
            return
        config = load_config()
        config[str(message.guild.id)] = str(message.channel.id)
        save_config(config)
        known_games[str(message.guild.id)] = {
            sheet["name"]: get_games_from_sheet(sheet["title"], sheet["colonne"])
            for sheet in SHEETS
        }
        await message.channel.send(
            "Ce salon est maintenant configure pour recevoir les notifications Archipelago !\n"
            "Le bot surveillera **Playable Worlds** et **Core Verified**."
        )

    if message.content.strip().startswith("!setrole"):
        if not message.author.guild_permissions.administrator:
            await message.channel.send("Tu dois etre administrateur pour faire ca.")
            return
        parts = message.content.strip().split()
        if len(parts) < 2:
            await message.channel.send(
                "Usage : `!setrole @RoleName` ou `!setrole ROLE_ID`"
            )
            return
        # Accepte soit une mention de role soit un ID brut
        raw = parts[1]
        if raw.startswith("<@&") and raw.endswith(">"):
            role_id = raw[3:-1]
        else:
            role_id = raw

        # Verifie que le role existe sur ce serveur
        role = message.guild.get_role(int(role_id))
        if not role:
            await message.channel.send("Role introuvable sur ce serveur. Verifie l'ID ou la mention.")
            return

        config = load_config()
        config[str(message.guild.id) + "_role"] = role_id
        save_config(config)
        await message.channel.send(
            f"Le role {role.mention} sera desormais ping pour chaque nouveau jeu."
        )

    if message.content.strip() == "!removerole":
        if not message.author.guild_permissions.administrator:
            await message.channel.send("Tu dois etre administrateur pour faire ca.")
            return
        config = load_config()
        key = str(message.guild.id) + "_role"
        if key in config:
            del config[key]
            save_config(config)
            await message.channel.send("Le role a ete retire. Le bot pingera @everyone a la place.")
        else:
            await message.channel.send("Aucun role n'etait configure.")

    if message.content.strip() == "!removechannel":
        if not message.author.guild_permissions.administrator:
            await message.channel.send("Tu dois etre administrateur pour faire ca.")
            return
        config = load_config()
        guild_id = str(message.guild.id)
        if guild_id in config:
            del config[guild_id]
            config.pop(guild_id + "_role", None)
            save_config(config)
            known_games.pop(guild_id, None)
            await message.channel.send("Les notifications ont ete desactivees sur ce serveur.")
        else:
            await message.channel.send("Aucun salon n'etait configure sur ce serveur.")

    if message.content.strip() == "!status":
        config = load_config()
        guild_id = str(message.guild.id)
        if guild_id in config:
            channel = client.get_channel(int(config[guild_id]))
            total   = sum(len(v) for v in known_games.get(guild_id, {}).values())
            role_id = config.get(guild_id + "_role")
            role    = message.guild.get_role(int(role_id)) if role_id else None
            ping    = role.mention if role else "@everyone"
            await message.channel.send(
                f"Bot actif - notifications dans {channel.mention}\n"
                f"Role ping : {ping}\n"
                f"{total} jeux suivis au total."
            )
        else:
            await message.channel.send(
                "Aucun salon configure. Un admin peut faire `!setchannel` dans le salon souhaite."
            )


# -- Boucle de verification --

async def check_for_new_games():
    await client.wait_until_ready()

    print("Resolution des onglets...")
    for sheet in SHEETS:
        title = get_sheet_name_by_gid(sheet["gid"])
        sheet["title"] = title if title else sheet["name"]
        print(f"  '{sheet['name']}' -> '{sheet['title']}'")

    wait_for_redis()
    config = load_config()
    print(f"Nombre de serveurs configures : {len([k for k in config if '_role' not in k])}")

    for guild_id in [k for k in config if "_role" not in k]:
        known_games[guild_id] = {
            sheet["name"]: get_games_from_sheet(sheet["title"], sheet["colonne"])
            for sheet in SHEETS
        }
        print(f"Serveur {guild_id} charge avec {sum(len(v) for v in known_games[guild_id].values())} jeux.")

    while not client.is_closed():
        await asyncio.sleep(CHECK_INTERVAL)
        config = load_config()
        try:
            for guild_id, channel_id in [(k, v) for k, v in config.items() if "_role" not in k]:
                channel = client.get_channel(int(channel_id))
                if not channel:
                    continue

                if guild_id not in known_games:
                    known_games[guild_id] = {
                        sheet["name"]: get_games_from_sheet(sheet["title"], sheet["colonne"])
                        for sheet in SHEETS
                    }
                    continue

                ping = get_ping(config, guild_id)

                for sheet in SHEETS:
                    current = get_games_from_sheet(sheet["title"], sheet["colonne"])
                    new     = current - known_games[guild_id][sheet["name"]]

                    for game in new:
                        print(f"[{guild_id}] Nouveau jeu dans '{sheet['name']}' : {game}")
                        await channel.send(
                            f"Nouveau jeu ajoute dans **{sheet['name']}** !\n"
                            f"> `{game}`\n"
                            f"{ping}"
                        )

                    known_games[guild_id][sheet["name"]] = current

        except Exception as e:
            print(f"Erreur : {e}")


@client.event
async def on_ready():
    print(f"Bot connecte : {client.user}")
    client.loop.create_task(check_for_new_games())


client.run(DISCORD_TOKEN)