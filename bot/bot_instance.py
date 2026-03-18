"""
Expose le client Discord comme singleton.
Les autres modules importent `bot_client` depuis ce fichier
pour éviter les imports circulaires entre views/modals et main.
"""
import discord

intents                 = discord.Intents.default()
intents.message_content = True

bot_client = discord.Client(intents=intents)
tree       = discord.app_commands.CommandTree(bot_client)