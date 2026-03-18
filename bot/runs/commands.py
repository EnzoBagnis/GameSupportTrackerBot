import re
from datetime import datetime
import discord
from discord import app_commands

from redis_client import load_runs, save_runs
from runs.models import new_run, build_run_embed
from runs.view import RunView # Correct import based on previous context
from runs.logic import close_run


def register_run_commands(tree: app_commands.CommandTree, get_client):
    """Enregistre les slash commands liées aux runs dans le CommandTree."""

    @tree.command(name="creer_run", description="Créer une annonce d'inscription pour une run Archipelago")
    @app_commands.checks.has_permissions(manage_events=True)
    @app_commands.describe(
        titre="Nom de la run",
        date_limite="Date limite (format: JJ/MM/AAAA HH:MM)",
        max_joueurs="Nombre max de joueurs (0 = illimité)",
        salon_annonce="Salon où poster l'annonce (vide = salon actuel)",
        salon_recap="Salon pour le récapitulatif (optionnel)"
    )
    async def creer_run(
        interaction: discord.Interaction,
        titre: str,
        date_limite: str = None,
        max_joueurs: int = 0,
        salon_annonce: discord.TextChannel = None,
        salon_recap: discord.TextChannel = None
    ):
        # Validation de la date si fournie
        formatted_deadline = None
        if date_limite:
            # Essayer de parser la date pour vérifier le format
            try:
                # Accepte JJ/MM/AAAA HH:MM ou JJ/MM HH:MM
                dt = None
                formats = ["%d/%m/%Y %H:%M", "%d/%m %H:%M"]
                for fmt in formats:
                    try:
                        dt = datetime.strptime(date_limite, fmt)
                        # Si l'année est manquante, on suppose l'année courante ou suivante
                        if "%Y" not in fmt:
                             now = datetime.now()
                             dt = dt.replace(year=now.year)
                             if dt < now:
                                 dt = dt.replace(year=now.year + 1)
                        break
                    except ValueError:
                        continue

                if not dt:
                    await interaction.response.send_message(
                        "Format de date invalide. Utilisez `JJ/MM/AAAA HH:MM` (ex: 20/04/2026 21:00)",
                        ephemeral=True
                    )
                    return
                # On stocke en string standard pour l'affichage/Redis
                formatted_deadline = dt.strftime("%d/%m/%Y %H:%M")
            except Exception:
                await interaction.response.send_message("Erreur lors de l'analyse de la date.", ephemeral=True)
                return

        destination_channel = salon_annonce or interaction.channel
        recap_channel_id = salon_recap.id if salon_recap else None

        # Création de l'objet Run
        run = new_run(
            title=titre,
            host_id=interaction.user.id,
            guild_id=interaction.guild.id,
            channel_id=destination_channel.id,
            deadline=formatted_deadline,
            max_players=max_joueurs or None,
            recap_channel_id=recap_channel_id,
        )

        try:
            embed = build_run_embed(run)
            view = RunView(run)
            msg = await destination_channel.send(embed=embed, view=view)

            run["message_id"] = msg.id
            runs = load_runs()
            runs[run["run_id"]] = run
            save_runs(runs)

            await interaction.response.send_message(
                f"Run **{run['title']}** créée dans {destination_channel.mention} ! (ID: `{run['run_id']}`)",
                ephemeral=True
            )
        except discord.Forbidden:
             await interaction.response.send_message(
                f"Je n'ai pas la permission d'envoyer des messages dans {destination_channel.mention}.",
                ephemeral=True
            )
        except Exception as e:
             await interaction.response.send_message(f"Erreur inattendue : {e}", ephemeral=True)


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
            await interaction.response.send_message("Run introuvable.", ephemeral=True)
            return
        if interaction.user.id != run["host_id"]:
            await interaction.response.send_message("Seul le host peut fermer la run.", ephemeral=True)
            return
        if not run["open"]:
            await interaction.response.send_message("Cette run est déjà fermée.", ephemeral=True)
            return

        client = get_client()
        success = await close_run(client, run_id)

        if success:
            await interaction.response.send_message("Run fermée ! Envoi du récap…", ephemeral=True)
        else:
            await interaction.response.send_message("Erreur lors de la fermeture de la run.", ephemeral=True)

    @creer_run.error
    async def creer_run_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "Tu n'as pas la permission de créer des runs (besoin de `Manage Events`).",
                ephemeral=True,
            )