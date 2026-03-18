import json
import time
import os
import redis as redis_lib
from config import REDIS_URL


class LocalRedis:
    """Simule un client Redis avec un fichier JSON local."""
    def __init__(self, file_path="local_db.json"):
        self.file_path = file_path
        self.data = {}
        self._load()

    def _load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception as e:
                print(f"Erreur lecture local_db.json : {e}")
                self.data = {}

    def _save(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Erreur sauvegarde local_db.json : {e}")

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value
        self._save()

    def ping(self):
        return True


def get_redis():
    if not REDIS_URL:
        return LocalRedis()
    return redis_lib.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=5)


def wait_for_redis(max_attempts: int = 10) -> bool:
    for attempt in range(1, max_attempts + 1):
        try:
            get_redis().ping()
            print(f"Redis connecté après {attempt} tentative(s).")
            return True
        except Exception as e:
            print(f"Redis pas encore prêt ({attempt}/{max_attempts}) : {e}")
            time.sleep(3)
    print("Impossible de se connecter à Redis.")
    return False


# ── Servers config ──────────────────────────────────────────

def load_config() -> dict:
    try:
        raw = get_redis().get("servers_config")
        if raw:
            return json.loads(raw)
    except Exception as e:
        print(f"Erreur lecture config Redis : {e}")
    return {}


def save_config(config: dict) -> None:
    try:
        get_redis().set("servers_config", json.dumps(config))
    except Exception as e:
        print(f"Erreur sauvegarde config Redis : {e}")


# ── Known games ─────────────────────────────────────────────

def load_known_games() -> dict:
    try:
        raw = get_redis().get("known_games")
        if raw:
            return {
                k: {s: set(v) for s, v in sv.items()}
                for k, sv in json.loads(raw).items()
            }
    except Exception as e:
        print(f"Erreur lecture known_games Redis : {e}")
    return {}


def save_known_games(kg: dict) -> None:
    try:
        serializable = {
            k: {s: list(v) for s, v in sv.items()}
            for k, sv in kg.items()
        }
        get_redis().set("known_games", json.dumps(serializable))
    except Exception as e:
        print(f"Erreur sauvegarde known_games Redis : {e}")


# ── Runs ────────────────────────────────────────────────────

def load_runs() -> dict:
    """Retourne toutes les runs. Clé : run_id (str) → dict run."""
    try:
        raw = get_redis().get("archipelago_runs")
        if raw:
            return json.loads(raw)
    except Exception as e:
        print(f"Erreur lecture runs Redis : {e}")
    return {}


def save_runs(runs: dict) -> None:
    try:
        get_redis().set("archipelago_runs", json.dumps(runs))
    except Exception as e:
        print(f"Erreur sauvegarde runs Redis : {e}")


def get_run_by_message(message_id: int) -> tuple[str | None, dict | None]:
    """Retrouve (run_id, run) depuis l'ID du message d'annonce."""
    for run_id, run in load_runs().items():
        if run.get("message_id") == message_id:
            return run_id, run
    return None, None