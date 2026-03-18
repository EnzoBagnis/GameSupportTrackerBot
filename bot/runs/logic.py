import discord
from runs.models import build_run_embed


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


async def send_recap(client: discord.Client, run: dict, guild: discord.Guild) -> None:
    """Génère et envoie le récap au salon dédié (si configuré) et en DM au host."""
    joueurs = run.get("players", {})
    titre   = run["title"]
    run_id  = run["run_id"]

    lines = [
        f"# 🏝️ Récap — {titre} (`{run_id}`)\n",
        f"**Host :** <@{run['host_id']}>",
        f"**Joueurs inscrits :** {len(joueurs)}\n",
    ]

    total_yamls    = []
    total_apworlds = []
    already_list   = []

    for uid, pdata in joueurs.items():
        jeux    = ", ".join(pdata.get("games", [])) or "—"
        yamls   = pdata.get("yaml_files", [])
        apws    = pdata.get("apworld_files", [])
        already = pdata.get("already_provided", False)
        note    = pdata.get("already_note", "")

        status_str = f"\n  ⚠️ *Déjà fournis déclaré : « {note} »*" if already else ""
        lines.append(f"• **{pdata['pseudo']}** (<@{uid}>) — {jeux}{status_str}")

        if yamls:
            lines.append(f"  📄 YAML : {', '.join(yamls)}")
            total_yamls.extend(yamls)
        if apws:
            lines.append(f"  🌐 APWorld : {', '.join(apws)}")
            total_apworlds.extend(apws)

        if already:
            already_list.append(f"{pdata['pseudo']} (<@{uid}>)")

    lines.append("")
    if already_list:
        lines.append(f"⚠️ **Joueurs ayant déclaré des fichiers déjà connus :** {', '.join(already_list)}")
    lines.append(f"📄 **Total YAML reçus :** {len(total_yamls)}")
    lines.append(f"🌐 **Total APWorld reçus :** {len(total_apworlds)}")

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