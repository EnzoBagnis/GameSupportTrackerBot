import io
import base64
import discord
from discord.ui import View, Button

from redis_client import load_runs, save_runs, get_run_by_message, load_user_files
from runs.models  import build_run_embed
from runs.logic   import refresh_run_message, send_recap, close_run  # Import close_run


class RunView(View):
    """Vue persistante attachée au message d'annonce de la run."""

    def __init__(self, run: dict):
        super().__init__(timeout=None)
        self.run_id = run["run_id"]

    # ── Helpers ────────────────────────────────────────────

    def _resolve_run(self, message_id: int) -> tuple[str, dict | None]:
        """Retrouve (run_id, run) depuis self.run_id ou le message_id en fallback."""
        runs = load_runs()
        run  = runs.get(self.run_id)
        if not run:
            run_id, run = get_run_by_message(message_id)
            if run:
                self.run_id = run_id
        return self.run_id, run

    # ── Boutons ────────────────────────────────────────────

    @discord.ui.button(label="S'inscrire", style=discord.ButtonStyle.success,
                       custom_id="btn_inscrire")
    async def inscrire(self, interaction: discord.Interaction, button: Button):
        run_id, run = self._resolve_run(interaction.message.id)

        if not run or not run["open"]:
            await interaction.response.send_message("Les inscriptions sont fermées.", ephemeral=True)
            return

        max_p = run.get("max_players")
        if max_p and len(run["players"]) >= max_p:
            await interaction.response.send_message("La run est complète.", ephemeral=True)
            return

        uid = str(interaction.user.id)
        if uid in run["players"]:
            await interaction.response.send_message(
                "Tu es déjà inscrit(e) ! Tu peux modifier ton inscription ou déposer des fichiers.",
                view=AlreadyInscritView(run_id),
                ephemeral=True,
            )
            return

        from runs.modals import InscriptionModal
        await interaction.response.send_modal(InscriptionModal(run_id))

    @discord.ui.button(label="Déposer fichiers", style=discord.ButtonStyle.primary,
                       custom_id="btn_upload")
    async def upload(self, interaction: discord.Interaction, button: Button):
        _, run = self._resolve_run(interaction.message.id)

        if not run:
            await interaction.response.send_message("Run introuvable.", ephemeral=True)
            return

        uid = str(interaction.user.id)
        if uid not in run.get("players", {}):
            await interaction.response.send_message("Inscris-toi d'abord !", ephemeral=True)
            return

        saved_files = load_user_files(uid)
        if saved_files:
            await interaction.response.send_message(
                "Tu as des fichiers sauvegardés ! Choisis ceux a envoyer au host, "
                "ou depose de nouveaux fichiers.",
                view=SavedFilesView(self.run_id, uid, saved_files),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "Pour envoyer tes fichiers :\n"
                "1. **Glisse et depose** tes fichiers `.yaml` ou `.apworld` directement dans la zone de texte de ce salon (ou utilise le bouton `+`).\n"
                "2. Appuie sur **Entree** pour envoyer le message.\n"
                "Le bot les detectera et les transmettra automatiquement au host.\n\n"
                "Si tes fichiers sont trop volumineux (sans Nitro), envoie-les directement en MP au host.",
                view=UploadView(self.run_id),
                ephemeral=True,
            )

    @discord.ui.button(label="Se désinscrire", style=discord.ButtonStyle.danger,
                       custom_id="btn_desinscrire")
    async def desinscrire(self, interaction: discord.Interaction, button: Button):
        run_id, run = self._resolve_run(interaction.message.id)

        if not run or not run["open"]:
            await interaction.response.send_message("Les inscriptions sont fermées.", ephemeral=True)
            return

        uid = str(interaction.user.id)
        if uid not in run.get("players", {}):
            await interaction.response.send_message("Tu n'es pas inscrit(e).", ephemeral=True)
            return

        del run["players"][uid]
        runs = load_runs()
        runs[run_id] = run
        save_runs(runs)

        from bot_instance import bot_client
        await refresh_run_message(bot_client, run)
        await interaction.response.send_message("Tu as été désinscrit(e).", ephemeral=True)

    @discord.ui.button(label="Fermer / Récap (Host)", style=discord.ButtonStyle.secondary, # Updated label
                       custom_id="btn_fermer")
    async def fermer(self, interaction: discord.Interaction, button: Button):
        run_id, run = self._resolve_run(interaction.message.id)

        # Verification host_id logic (existing)
        if not run:
            await interaction.response.send_message("Run introuvable.", ephemeral=True)
            return
        if interaction.user.id != run["host_id"]:
            await interaction.response.send_message("Seul le host peut fermer la run.", ephemeral=True)
            return

        from bot_instance import bot_client
        success = await close_run(bot_client, run_id)

        if success:
             await interaction.response.send_message("Run fermée ! Génération du récap…", ephemeral=True)
        else:
             await interaction.response.send_message("Erreur lors de la fermeture.", ephemeral=True)


class AlreadyInscritView(View):
    """Proposé au joueur déjà inscrit : modifier ou déposer des fichiers."""

    def __init__(self, run_id: str):
        super().__init__(timeout=120)
        self.run_id = run_id

    @discord.ui.button(label="Modifier mon inscription", style=discord.ButtonStyle.primary)
    async def modifier(self, interaction: discord.Interaction, button: Button):
        from runs.modals import InscriptionModal
        await interaction.response.send_modal(InscriptionModal(self.run_id))

    @discord.ui.button(label="Déposer mes fichiers", style=discord.ButtonStyle.success)
    async def deposer(self, interaction: discord.Interaction, button: Button):
        uid = str(interaction.user.id)
        saved_files = load_user_files(uid)

        if saved_files:
            await interaction.response.send_message(
                "Tu as des fichiers sauvegardés ! Choisis ceux a envoyer au host, "
                "ou depose de nouveaux fichiers.",
                view=SavedFilesView(self.run_id, uid, saved_files),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "Envoie tes fichiers YAML / APWorld en piece jointe dans ce salon.\n"
                "Si tes fichiers sont trop volumineux (sans Nitro), envoie-les directement en MP au host.",
                view=UploadView(self.run_id),
                ephemeral=True,
            )


class UploadView(View):
    """Confirmation après dépôt de fichiers."""

    def __init__(self, run_id: str):
        super().__init__(timeout=300)
        self.run_id = run_id

    @discord.ui.button(label="J'ai envoyé mes fichiers", style=discord.ButtonStyle.success)
    async def confirmer(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(
            "Merci ! Le bot transmettra tes fichiers au host dès réception.",
            ephemeral=True,
        )


class SavedFilesView(View):
    """Permet de choisir parmi les fichiers sauvegardés pour les envoyer au host."""

    def __init__(self, run_id: str, user_id: str, saved_files: list):
        super().__init__(timeout=300)
        self.run_id = run_id
        self.user_id = user_id
        self.saved_files = saved_files
        self.selected_filenames: list[str] = []

        options = [
            discord.SelectOption(label=f["filename"], value=f["filename"])
            for f in saved_files[:25]
        ]
        select = discord.ui.Select(
            placeholder="Choisis tes fichiers...",
            options=options,
            min_values=1,
            max_values=len(options),
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction):
        self.selected_filenames = interaction.data["values"]
        await interaction.response.defer()

    @discord.ui.button(label="Envoyer la sélection", style=discord.ButtonStyle.success, row=2)
    async def envoyer(self, interaction: discord.Interaction, button: Button):
        if not self.selected_filenames:
            await interaction.response.send_message("Sélectionne d'abord des fichiers.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        runs = load_runs()
        run = runs.get(self.run_id)
        if not run or not run["open"]:
            await interaction.followup.send("Cette run est fermée ou introuvable.", ephemeral=True)
            return

        uid = self.user_id
        if uid not in run.get("players", {}):
            await interaction.followup.send("Tu n'es pas inscrit(e) a cette run.", ephemeral=True)
            return

        pdata = run["players"][uid]
        saved_map = {f["filename"]: f for f in self.saved_files}

        files_to_send = []
        for fname in self.selected_filenames:
            f = saved_map.get(fname)
            if not f:
                continue
            data = base64.b64decode(f["data"])
            files_to_send.append(discord.File(io.BytesIO(data), filename=fname))

            if f["type"] == "yaml" and fname not in pdata.get("yaml_files", []):
                pdata.setdefault("yaml_files", []).append(fname)
            elif f["type"] == "apworld" and fname not in pdata.get("apworld_files", []):
                pdata.setdefault("apworld_files", []).append(fname)

        runs[self.run_id] = run
        save_runs(runs)

        if not files_to_send:
            await interaction.followup.send("Aucun fichier valide sélectionné.", ephemeral=True)
            return

        from bot_instance import bot_client
        host = bot_client.get_user(run["host_id"])
        if not host:
            try:
                host = await bot_client.fetch_user(run["host_id"])
            except Exception:
                host = None

        if host:
            try:
                dm_content = (
                    f"**Fichiers reçus (depuis sauvegarde)** pour la run **{run['title']}** !\n"
                    f"Joueur : <@{uid}> ({pdata['pseudo']})\n"
                    f"Jeux : {', '.join(pdata['games'])}"
                )
                await host.send(dm_content, files=files_to_send)
                await interaction.followup.send(
                    f"{len(files_to_send)} fichier(s) envoyé(s) au host.",
                    ephemeral=True,
                )
            except discord.Forbidden:
                await interaction.followup.send(
                    "Impossible d'envoyer les fichiers au host (DMs fermés).",
                    ephemeral=True,
                )
        else:
            await interaction.followup.send("Host introuvable.", ephemeral=True)

    @discord.ui.button(label="Déposer de nouveaux fichiers", style=discord.ButtonStyle.secondary, row=2)
    async def nouveau(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(
            "Pour envoyer tes fichiers :\n"
            "1. **Glisse et dépose** tes fichiers `.yaml` ou `.apworld` directement dans la zone de texte de ce salon.\n"
            "2. Appuie sur **Entrée** pour envoyer le message.\n"
            "Le bot les détectera et les transmettra automatiquement au host.",
            view=UploadView(self.run_id),
            ephemeral=True,
        )