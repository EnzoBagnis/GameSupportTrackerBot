import discord
from discord import app_commands

from redis_client import load_runs, save_runs
from runs.logic   import refresh_run_message, send_recap
from runs.modals  import CreerRunModal


def register_run_commands(tree: app_commands.CommandTree, get_client):
    """Enregistre les slash commands liées aux runs dans le CommandTree."""

    @tree.command(name="creer_run", description="Créer une annonce d'inscription pour une run Archipelago")
    @app_commands.checks.has_permissions(manage_events=True)
    async def creer_run(interaction: discord.Interaction):
        await interaction.response.send_modal(CreerRunModal())

    @tree.command(name="runs_actives", description="Lister les runs ouvertes sur ce serveur")
    async def runs_actives(interaction: discord.Interaction):
        runs    = load_runs()
        gid     = interaction.guild.id
        actives = [
            (rid, r) for rid, r in runs.items()
            if r["guild_id"] == gid and r["open"]
        ]

        if not actives:
            await interaction.response.send_message("Aucune run active sur ce serveur.", ephemeral=True)
            return

        lines = []
        for rid, r in actives:
            nb    = len(r.get("players", {}))
            max_p = r.get("max_players")
            max_s = f"/{max_p}" if max_p else ""
            lines.append(
                f"• **{r['title']}** — `{rid}` — {nb}{max_s} joueur(s) — Host : <@{r['host_id']}>"
            )

        await interaction.response.send_message(
            "**Runs actives :**\n" + "\n".join(lines),
            ephemeral=True,
        )

    @tree.command(name="fermer_run", description="Fermer une run et générer le récap (host uniquement)")
    @app_commands.describe(run_id="L'ID de la run à fermer")
    async def fermer_run(interaction: discord.Interaction, run_id: str):
        runs = load_runs()
        run  = runs.get(run_id)

        if not run:
            await interaction.response.send_message("❌ Run introuvable.", ephemeral=True)
            return
        if interaction.user.id != run["host_id"]:
            await interaction.response.send_message("❌ Seul le host peut fermer la run.", ephemeral=True)
            return
        if not run["open"]:
            await interaction.response.send_message("Cette run est déjà fermée.", ephemeral=True)
            return

        run["open"] = False
        runs[run_id] = run
        save_runs(runs)

        client = get_client()
        await refresh_run_message(client, run)
        await interaction.response.send_message("🔒 Run fermée ! Envoi du récap…", ephemeral=True)
        await send_recap(client, run, interaction.guild)

    @creer_run.error
    async def creer_run_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Tu n'as pas la permission de créer des runs (besoin de `Manage Events`).",
                ephemeral=True,
            )