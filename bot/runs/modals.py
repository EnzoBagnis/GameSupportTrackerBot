import discord
from discord.ui import Modal, TextInput

from redis_client import load_runs, save_runs
from runs.models  import new_run, new_player, build_run_embed
from runs.logic   import refresh_run_message



class InscriptionModal(Modal, title="S'inscrire à la run"):
    pseudo = TextInput(label="Ton pseudo Archipelago",               placeholder="ex: Pikachu_AP",               max_length=64)
    games  = TextInput(label="Jeu(x) que tu amènes",                placeholder="ex: Pokemon FRLG, Celeste",    max_length=200)
    deja   = TextInput(
        label       = "As-tu déjà fourni tes fichiers au host ?",
        placeholder = "Oui / Non — si Oui, précise quels fichiers sont déjà connus",
        required    = False,
        max_length  = 200,
        style       = discord.TextStyle.paragraph,
    )

    def __init__(self, run_id: str):
        super().__init__()
        self.run_id = run_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        runs = load_runs()
        run  = runs.get(self.run_id)
        if not run or not run["open"]:
            await interaction.followup.send("❌ Cette run est fermée ou introuvable.", ephemeral=True)
            return

        uid         = str(interaction.user.id)
        deja_val    = self.deja.value.strip().lower()
        already     = deja_val.startswith("oui") or deja_val.startswith("yes")
        games_list  = [g.strip() for g in self.games.value.split(",") if g.strip()]

        if uid not in run["players"]:
            run["players"][uid] = new_player(
                pseudo           = self.pseudo.value.strip(),
                games            = games_list,
                already_provided = already,
                already_note     = self.deja.value.strip(),
            )
        else:
            # Mise à jour sans écraser les fichiers déjà déposés
            p = run["players"][uid]
            p["pseudo"]           = self.pseudo.value.strip()
            p["games"]            = games_list
            p["already_provided"] = already
            p["already_note"]     = self.deja.value.strip()

        runs[self.run_id] = run
        save_runs(runs)

        from bot_instance import bot_client
        await refresh_run_message(bot_client, run)

        from runs.views import UploadView
        if already:
            msg = (
                "✅ Inscription enregistrée !\n"
                "Tu as indiqué que tes fichiers ont déjà été fournis. "
                "Tu peux quand même en déposer de nouveaux ci-dessous si besoin."
            )
        else:
            msg = (
                "✅ Inscription enregistrée !\n"
                "**Dépose maintenant tes fichiers** YAML et/ou APWorld en pièce jointe "
                "dans n'importe quel salon — le bot les transmettra automatiquement au host."
            )

        await interaction.followup.send(msg, view=UploadView(self.run_id), ephemeral=True)