"""Per-user Epic token storage (local JSON, chmod 600)."""

from __future__ import annotations

import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TOKENS_FILE = BASE_DIR / "tokens.json"


def load_all() -> dict:
    if TOKENS_FILE.exists():
        try:
            return json.loads(TOKENS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_all(data: dict) -> None:
    TOKENS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(TOKENS_FILE, 0o600)
    except Exception:
        pass


def get(user_id: int | str) -> dict | None:
    return load_all().get(str(user_id))


def put(user_id: int | str, entry: dict) -> None:
    data = load_all()
    data[str(user_id)] = entry
    save_all(data)


def delete(user_id: int | str) -> bool:
    data = load_all()
    if str(user_id) in data:
        del data[str(user_id)]
        save_all(data)
        return True
    return False
