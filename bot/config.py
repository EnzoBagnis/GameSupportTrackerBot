import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN  = os.getenv("DISCORD_TOKEN")
API_KEY        = os.getenv("GOOGLE_API_KEY")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 60))
REDIS_URL      = os.getenv("REDIS_URL")

SPREADSHEET_ID = "1iuzDTOAvdoNe8Ne8i461qGNucg5OuEoF-Ikqs8aUQZw"

SHEETS = [
    {"name": "Playable Worlds", "gid": "58422002",   "colonne": 0},
    {"name": "Core Verified",   "gid": "1675722515", "colonne": 0},
]

YAML_EXTENSIONS    = (".yaml", ".yml")
APWORLD_EXTENSIONS = (".apworld",)