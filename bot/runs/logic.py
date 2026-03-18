import discord
from runs.models import build_run_embed
from redis_client import load_runs, save_runs


async def close_run(client: discord.Client, run_id: str) -> bool:
    """
    Ferme la run, met à jour le statut, et envoie le récap.
    Retourne True si la fermeture a réussi.
    """
    runs = load_runs()
    run = runs.get(run_id)

    if not run or not run["open"]:
        return False

    run["open"] = False
    runs[run_id] = run
    save_runs(runs)

    # Mise à jour du message d'annonce
    await refresh_run_message(client, run)

    # Envoi du récap
    await send_recap(client, run)

    return True


async def refresh_run_message(client: discord.Client, run: dict) -> None:
    """Met à jour l'embed du message d'annonce avec les données actuelles."""
    try:
        # Import ici pour éviter la circularité views ↔ logic
        from runs.view import RunView

        channel = client.get_channel(run["channel_id"])
        if not channel:
            return
        msg   = await channel.fetch_message(run["message_id"])
        embed = build_run_embed(run)
        view  = RunView(run)
        await msg.edit(embed=embed, view=view)
    except Exception as e:
        print(f"Erreur refresh message run '{run.get('run_id')}' : {e}")


async def send_recap(client: discord.Client, run: dict) -> None:
    """Génère et envoie le récap au salon dédié (si configuré) et en DM au host."""
    joueurs = run.get("players", {})
    titre   = run["title"]
    run_id  = run["run_id"]

    lines = [
        f"# Récap — {titre}\n",
        f"**Joueurs inscrits :** {len(joueurs)}\n",
    ]

    for uid, pdata in joueurs.items():
        jeux    = ", ".join(pdata.get("games", [])) or "—"
        already_note = pdata.get("already_note", "")
        note_str = f" [Note: {already_note}]" if already_note else ""

        lines.append(f"• **{pdata['pseudo']}** — {jeux}{note_str}")

    recap_text = "\n".join(lines)

    async def send_chunked(target, text: str) -> None:
        """Envoie un texte en découpant si > 2000 caractères."""
        chunks = [text[i:i + 1990] for i in range(0, len(text), 1990)]
        for chunk in chunks:
            await target.send(chunk)

    # Salon récap (optionnel)
    recap_cid = run.get("recap_channel_id")
    if recap_cid:
        recap_channel = client.get_channel(recap_cid)
        if recap_channel:
            try:
                await send_chunked(recap_channel, recap_text)
            except Exception as e:
                print(f"Erreur envoi récap salon : {e}")

    # DM host (toujours)
    host = client.get_user(run["host_id"])
    if not host:
        try:
            host = await client.fetch_user(run["host_id"])
        except Exception:
            host = None

    if host:
        try:
            await send_chunked(host, f"🔒 **Run fermée — {titre}**\n\n" + recap_text)
        except discord.Forbidden:
            print(f"Impossible d'envoyer le récap en DM au host {run['host_id']}")