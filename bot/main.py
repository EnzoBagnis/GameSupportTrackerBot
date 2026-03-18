import asyncio
import io
import discord
from discord.ext import tasks # Import tasks for background loop
from datetime import datetime

from bot_instance import bot_client, tree
from config       import DISCORD_TOKEN, CHECK_INTERVAL, SHEETS, YAML_EXTENSIONS, APWORLD_EXTENSIONS
from redis_client import (
    wait_for_redis, load_config, save_config,
    load_known_games, save_known_games,
    load_runs, save_runs,
)
from sheets               import get_sheet_name_by_gid, get_games_from_sheet
from runs.view            import RunView
from runs.commands        import register_run_commands
from runs.logic           import close_run # Import close_run
from commands.admin       import register_admin_commands

# Dictionnaire partagé des jeux connus (guild_id → {sheet_name → set})
known_games: dict = {}

# ── Enregistrement des commandes ────────────────────────────
register_admin_commands(tree, known_games)
register_run_commands(tree, lambda: bot_client)


# ── Listener fichiers ────────────────────────────────────────

@bot_client.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.attachments:
        return

    yamls    = [a for a in message.attachments if a.filename.lower().endswith(YAML_EXTENSIONS)]
    apworlds = [a for a in message.attachments if a.filename.lower().endswith(APWORLD_EXTENSIONS)]

    if not yamls and not apworlds:
        return

    runs = load_runs()
    uid  = str(message.author.id)

    # Trouve la run ouverte à laquelle ce joueur est inscrit
    target_run_id = next(
        (rid for rid, r in runs.items() if r["open"] and uid in r.get("players", {})),
        None,
    )
    if not target_run_id:
        return

    run   = runs[target_run_id]
    pdata = run["players"][uid]

    files_to_send_to_host = []

    for a in yamls:
        if a.filename not in pdata["yaml_files"]:
            pdata["yaml_files"].append(a.filename)
            files_to_send_to_host.append(a)

    for a in apworlds:
        if a.filename not in pdata["apworld_files"]:
            pdata["apworld_files"].append(a.filename)
            files_to_send_to_host.append(a)

    runs[target_run_id] = run
    save_runs(runs)

    # 🟢 NEW: File deletion logic guaranteed via try/finally or direct call
    # Envoi au host en DM
    host = bot_client.get_user(run["host_id"])
    if not host:
        try:
            host = await bot_client.fetch_user(run["host_id"])
        except Exception:
            host = None

    if host and files_to_send_to_host:
        try:
            already_flag = pdata.get("already_provided", False)
            note_str     = (
                f"\n⚠️ *Ce joueur a déclaré avoir déjà fourni des fichiers : « {pdata.get('already_note', '')} »*"
                if already_flag else ""
            )
            dm_content = (
                f"📎 **Nouveaux fichiers reçus** pour la run **{run['title']}** !\n"
                f"Joueur : <@{uid}> ({pdata['pseudo']})\n"
                f"Jeux : {', '.join(pdata['games'])}{note_str}"
            )

            # Read files to send
            attachments_to_send = []
            for att in files_to_send_to_host:
                 data = await att.read()
                 attachments_to_send.append(discord.File(io.BytesIO(data), filename=att.filename))

            await host.send(dm_content, files=attachments_to_send)
        except discord.Forbidden:
            print(f"Impossible d'envoyer un DM au host {run['host_id']}")

    # Auto-delete user message to keep channel clean
    # Move this logic UP or inside a critical block if we want it guaranteed even if host DM fails (which is caught)
    # Since DM errors are caught above, this runs.
    # However, if 'message.delete()' failed before (maybe permission issue?), let's retry or log.
    try:
        if message.channel.permissions_for(message.guild.me).manage_messages:
             await message.delete()
        else:
             print(f"Manque la permission 'Manage Messages' dans {message.channel}")
    except discord.NotFound:
        pass # Already deleted
    except discord.Forbidden:
        print(f"Impossible de supprimer le message dans {message.channel} (Permission manquante?)")
    except Exception as e:
        print(f"Error deleting message: {e}")


# ── Background Task: Check Deadlines ────────────────────────
@tasks.loop(seconds=60)
async def check_deadlines():
    runs = load_runs()
    now = datetime.now()

    for run_id, run in runs.items():
        if run["open"] and run.get("deadline"):
            try:
                deadline_dt = datetime.strptime(run["deadline"], "%d/%m/%Y %H:%M")
                if now > deadline_dt:
                    print(f"Deadline atteinte pour la run {run_id} ({run['deadline']}). Fermeture...")
                    await close_run(bot_client, run_id)
            except ValueError:
                print(f"Format de date invalide pour la run {run_id}: {run['deadline']}")
            except Exception as e:
                print(f"Erreur lors de la fermeture automatique de la run {run_id}: {e}")

@check_deadlines.before_loop
async def before_check_deadlines():
    await bot_client.wait_until_ready()


# ── Boucle Google Sheets ─────────────────────────────────────

async def check_for_new_games():
    await bot_client.wait_until_ready()

    print("Résolution des onglets Google Sheets...")
    for sheet in SHEETS:
        title          = get_sheet_name_by_gid(sheet["gid"])
        sheet["title"] = title if title else sheet["name"]
        print(f"  '{sheet['name']}' → '{sheet['title']}'")

    wait_for_redis()
    config = load_config()
    print(f"Serveurs configurés : {len([k for k in config if '_role' not in k])}")

    saved = load_known_games()
    if saved:
        known_games.update(saved)
        print(f"known_games restauré depuis Redis ({len(saved)} serveur(s)).")

    for guild_id in [k for k in config if "_role" not in k]:
        if guild_id not in known_games:
            known_games[guild_id] = {
                sheet["name"]: get_games_from_sheet(sheet["title"], sheet["colonne"])
                for sheet in SHEETS
            }
            print(f"Serveur {guild_id} chargé ({sum(len(v) for v in known_games[guild_id].values())} jeux).")

    save_known_games(known_games)

    while not bot_client.is_closed():
        await asyncio.sleep(CHECK_INTERVAL)
        config  = load_config()
        changed = False

        try:
            for guild_id, channel_id in [(k, v) for k, v in config.items() if "_role" not in k]:
                channel = bot_client.get_channel(int(channel_id))
                if not channel:
                    continue

                if guild_id not in known_games:
                    known_games[guild_id] = {
                        sheet["name"]: get_games_from_sheet(sheet["title"], sheet["colonne"])
                        for sheet in SHEETS
                    }
                    save_known_games(known_games)
                    continue

                role_id = config.get(guild_id + "_role")
                ping    = f"<@&{role_id}>" if role_id else "@everyone"

                for sheet in SHEETS:
                    current = get_games_from_sheet(sheet["title"], sheet["colonne"])
                    new     = current - known_games[guild_id][sheet["name"]]

                    for game in new:
                        print(f"[{guild_id}] Nouveau jeu dans '{sheet['name']}' : {game}")
                        await channel.send(
                            f"New game added in **{sheet['name']}** !\n> `{game}`\n{ping}"
                        )

                    known_games[guild_id][sheet["name"]] = current
                    if new:
                        changed = True

        except Exception as e:
            print(f"Erreur boucle Sheets : {e}")

        if changed:
            save_known_games(known_games)


# ── on_ready ─────────────────────────────────────────────────

@bot_client.event
async def on_ready():
    print(f'Bot connect : {bot_client.user}')
    runs = load_runs()
    print(f"{len(runs)} run(s) active(s) restaure(s).")
    try:
        synced = await tree.sync()
        print(f"Slash commands synchronises.")
    except Exception as e:
        print(e)

    # Start background tasks
    if not check_deadlines.is_running():
        check_deadlines.start()


# ── Lancement ─────────────────────────────────────────────────

bot_client.run(DISCORD_TOKEN)