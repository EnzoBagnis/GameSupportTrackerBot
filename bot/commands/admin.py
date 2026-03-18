import discord
from discord import app_commands

from redis_client import load_config, save_config, load_known_games, save_known_games
from sheets       import get_games_from_sheet
from config       import SHEETS


def register_admin_commands(tree: app_commands.CommandTree, known_games: dict):
    """Enregistre les commandes admin dans le CommandTree."""

    @tree.command(name="setchannel", description="Set this channel to receive Archipelago game notifications")
    @app_commands.checks.has_permissions(administrator=True)
    async def setchannel(interaction: discord.Interaction):
        config                              = load_config()
        config[str(interaction.guild.id)]   = str(interaction.channel.id)
        save_config(config)

        known_games[str(interaction.guild.id)] = {
            sheet["name"]: get_games_from_sheet(sheet["title"], sheet["colonne"])
            for sheet in SHEETS
            if "title" in sheet
        }
        save_known_games(known_games)

        await interaction.response.send_message(
            "This channel is now configured to receive Archipelago notifications.\n"
            "The bot will monitor **Playable Worlds** and **Core Verified**."
        )

    @tree.command(name="setrole", description="Set a role to ping when a new game is added")
    @app_commands.describe(role="The role to ping")
    @app_commands.checks.has_permissions(administrator=True)
    async def setrole(interaction: discord.Interaction, role: discord.Role):
        config                                              = load_config()
        config[str(interaction.guild.id) + "_role"]        = str(role.id)
        save_config(config)
        await interaction.response.send_message(f"{role.mention} will now be pinged when a new game is added.")

    @tree.command(name="removerole", description="Remove the custom role and revert to @everyone")
    @app_commands.checks.has_permissions(administrator=True)
    async def removerole(interaction: discord.Interaction):
        config = load_config()
        key    = str(interaction.guild.id) + "_role"
        if key in config:
            del config[key]
            save_config(config)
            await interaction.response.send_message("Role removed. The bot will now ping @everyone.")
        else:
            await interaction.response.send_message("No role was configured.")

    @tree.command(name="removechannel", description="Disable Archipelago notifications on this server")
    @app_commands.checks.has_permissions(administrator=True)
    async def removechannel(interaction: discord.Interaction):
        config   = load_config()
        guild_id = str(interaction.guild.id)
        if guild_id in config:
            del config[guild_id]
            config.pop(guild_id + "_role", None)
            save_config(config)
            known_games.pop(guild_id, None)
            await interaction.response.send_message("Notifications have been disabled on this server.")
        else:
            await interaction.response.send_message("No channel was configured.")

    @tree.command(name="status", description="Show the current bot configuration for this server")
    async def status(interaction: discord.Interaction):
        config   = load_config()
        guild_id = str(interaction.guild.id)
        if guild_id in config:
            channel = interaction.client.get_channel(int(config[guild_id]))
            total   = sum(len(v) for v in known_games.get(guild_id, {}).values())
            role_id = config.get(guild_id + "_role")
            role    = interaction.guild.get_role(int(role_id)) if role_id else None
            ping    = role.mention if role else "@everyone"
            await interaction.response.send_message(
                f"Bot active — notifications in {channel.mention}\n"
                f"Ping : {ping}\n"
                f"{total} games tracked."
            )
        else:
            await interaction.response.send_message(
                "No channel configured. An admin can run `/setchannel` to set one up."
            )

    # ── Error handlers ──────────────────────────────────────

    @setchannel.error
    @setrole.error
    @removerole.error
    @removechannel.error
    async def permission_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need administrator permissions to use this command.",
                ephemeral=True,
            )