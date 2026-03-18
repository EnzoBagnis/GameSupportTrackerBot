import uuid
import discord


def new_run(
    title: str,
    host_id: int,
    guild_id: int,
    channel_id: int,
    deadline: str | None        = None,
    max_players: int | None     = None,
    recap_channel_id: int | None = None,
) -> dict:
    """Crée un dictionnaire run avec les valeurs par défaut."""
    return {
        "run_id"          : str(uuid.uuid4())[:8],
        "title"           : title,
        "deadline"        : deadline,
        "max_players"     : max_players,
        "host_id"         : host_id,
        "guild_id"        : guild_id,
        "channel_id"      : channel_id,
        "recap_channel_id": recap_channel_id,
        "message_id"      : None,
        "open"            : True,
        # uid (str) → {pseudo, games, already_provided, already_note, yaml_files, apworld_files}
        "players"         : {},
    }


def new_player(pseudo: str, games: list[str], already_provided: bool, already_note: str) -> dict:
    return {
        "pseudo"          : pseudo,
        "games"           : games,
        "already_provided": already_provided,
        "already_note"    : already_note,
        "yaml_files"      : [],
        "apworld_files"   : [],
    }


def build_run_embed(run: dict) -> discord.Embed:
    """Construit l'embed d'annonce affiché dans le salon."""
    deadline = run.get("deadline") or "Pas de date limite"
    max_p    = run.get("max_players")
    joueurs  = run.get("players", {})
    nb       = len(joueurs)
    max_str  = f"/{max_p}" if max_p else ""
    statut   = "🟢 Ouverte" if run["open"] else "🔴 Fermée"

    embed = discord.Embed(
        title       = f"🏝️ Inscription — {run['title']}",
        description = (
            "Clique sur **S'inscrire** pour participer à cette run Archipelago.\n"
            "Tu pourras préciser tes jeux et déposer tes fichiers YAML / APWorld."
        ),
        color = discord.Color.teal() if run["open"] else discord.Color.greyple(),
    )
    embed.add_field(name="📅 Date limite",  value=deadline,              inline=True)
    embed.add_field(name="👥 Inscrits",     value=f"{nb}{max_str}",      inline=True)
    embed.add_field(name="🔑 Host",         value=f"<@{run['host_id']}>", inline=True)
    embed.add_field(name="📌 Statut",       value=statut,                inline=True)

    if joueurs:
        lines = []
        for uid, pdata in joueurs.items():
            jeux  = ", ".join(pdata.get("games", [])) or "—"
            yamls = pdata.get("yaml_files", [])
            apws  = pdata.get("apworld_files", [])

            fichiers = []
            if yamls:
                fichiers.append(f"📄 {len(yamls)} YAML")
            if apws:
                fichiers.append(f"🌐 {len(apws)} APWorld")
            fichiers_str = f" [{', '.join(fichiers)}]" if fichiers else ""

            deja_str = " *(fichiers déjà connus)*" if pdata.get("already_provided") else ""
            lines.append(f"• <@{uid}> — {jeux}{fichiers_str}{deja_str}")

        embed.add_field(name="📋 Joueurs", value="\n".join(lines), inline=False)

    embed.set_footer(text=f"Run ID : {run['run_id']}")
    return embed