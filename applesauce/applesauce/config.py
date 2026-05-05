from __future__ import annotations

import json
import os
from pathlib import Path


CONFIG_ENV_VAR = "APPLESAUCE_CONFIG"


def config_path() -> Path:
    override = os.getenv(CONFIG_ENV_VAR)
    if override:
        return Path(override).expanduser()

    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / "applesauce" / "config.json"

    return Path.home() / ".config" / "applesauce" / "config.json"


def load_config() -> dict[str, str]:
    path = config_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items() if isinstance(value, str)}


def save_config(config: dict[str, str]) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return path


def get_saved_api_key() -> str | None:
    return load_config().get("openai_api_key")


def save_api_key(api_key: str) -> Path:
    config = load_config()
    config["openai_api_key"] = api_key.strip()
    return save_config(config)
