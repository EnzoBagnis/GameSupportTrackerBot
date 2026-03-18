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
    statut   = "Ouverte" if run["open"] else "Fermée"

    embed = discord.Embed(
        title=f"Archipelago Run — {run['title']}",
        color=discord.Color.green() if run["open"] else discord.Color.red()
    )
    embed.add_field(name="Date limite", value=deadline, inline=True)
    embed.add_field(name="Joueurs inscrits", value=f"{nb}{max_str}", inline=True)
    embed.add_field(name="Statut", value=statut, inline=True)
    embed.add_field(name="Host", value=f"<@{run['host_id']}>", inline=False)

    if nb > 0:
        names = [f"• {p['pseudo']}" for p in joueurs.values()]
        # Limite d'affichage simple
        txt = "\n".join(names[:20])
        if len(names) > 20:
            txt += f"\n... et {len(names) - 20} autres"
        embed.add_field(name="Participants", value=txt, inline=False)

    embed.set_footer(text=f"ID: {run['run_id']}")
    return embed