from __future__ import annotations

from dataclasses import dataclass

from ..config import load_config, save_config


DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_API_KEY = "local-not-needed"


@dataclass(frozen=True)
class SavedLocalSettings:
    base_url: str = DEFAULT_BASE_URL
    model: str = ""
    api_key: str = DEFAULT_API_KEY


def load_local_settings() -> SavedLocalSettings:
    config = load_config()
    return SavedLocalSettings(
        base_url=config.get("run_it_yaself_base_url", DEFAULT_BASE_URL),
        model=config.get("run_it_yaself_model", ""),
        api_key=config.get("run_it_yaself_api_key", DEFAULT_API_KEY),
    )


def save_local_settings(*, base_url: str, model: str, api_key: str) -> None:
    config = load_config()
    config["run_it_yaself_base_url"] = base_url.strip() or DEFAULT_BASE_URL
    config["run_it_yaself_model"] = model.strip()
    config["run_it_yaself_api_key"] = api_key.strip() or DEFAULT_API_KEY
    save_config(config)
