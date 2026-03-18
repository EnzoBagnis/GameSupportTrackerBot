import requests
from config import API_KEY, SPREADSHEET_ID


def get_sheet_name_by_gid(gid: str) -> str | None:
    url      = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}?key={API_KEY}"
    response = requests.get(url)
    for sheet in response.json().get("sheets", []):
        if str(sheet["properties"]["sheetId"]) == gid:
            return sheet["properties"]["title"]
    return None


def get_games_from_sheet(sheet_title: str, colonne: int) -> set:
    url = (
        f"https://sheets.googleapis.com/v4/spreadsheets/"
        f"{SPREADSHEET_ID}/values/{requests.utils.quote(sheet_title)}!A:Z?key={API_KEY}"
    )
    response = requests.get(url)
    rows     = response.json().get("values", [])
    return {row[colonne] for row in rows[1:] if len(row) > colonne}