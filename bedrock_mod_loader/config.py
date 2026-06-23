"""A tiny persisted preferences file so the CLI/GUI can remember your last setup
(game directory, last world used) instead of asking every time.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".bedrock_mod_loader" / "config.json"


def config_path() -> Path:
    override = os.environ.get("BEDROCK_MOD_LOADER_CONFIG")
    return Path(override) if override else DEFAULT_CONFIG_PATH


def load_config() -> dict:
    path = config_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_config(data: dict) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def update_config(**changes) -> dict:
    """Merge non-None values into the saved config and write it back."""
    data = load_config()
    data.update({key: value for key, value in changes.items() if value is not None})
    save_config(data)
    return data
