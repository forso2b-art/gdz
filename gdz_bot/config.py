from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(slots=True)
class Config:
    bot_token: str
    openrouter_api_keys: tuple[str, ...]
    openrouter_http_referer: str
    openrouter_app_title: str
    admin_ids: set[int]
    sqlite_path: Path
    timezone: str


def _parse_admin_ids(raw_value: str) -> set[int]:
    values = set()
    for chunk in raw_value.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        values.add(int(chunk))
    return values


def _load_openrouter_keys() -> tuple[str, ...]:
    keys: list[str] = []
    for index in range(1, 6):
        value = (
            os.getenv(f"OPENROUTER_API_{index}", "").strip()
            or os.getenv(f"API_{index}", "").strip()
        )
        if value:
            keys.append(value)

    legacy_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if legacy_key and not keys:
        keys.append(legacy_key)

    return tuple(keys)


def load_config() -> Config:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    openrouter_api_keys = _load_openrouter_keys()
    openrouter_http_referer = os.getenv("OPENROUTER_HTTP_REFERER", "https://example.com").strip()
    openrouter_app_title = os.getenv("OPENROUTER_APP_TITLE", "GDZ Bot").strip()
    admin_ids_raw = os.getenv("ADMIN_IDS", "8753690478")
    sqlite_path = Path(os.getenv("SQLITE_PATH", "data/gdz.sqlite3"))
    timezone = os.getenv("BOT_TIMEZONE", "Europe/Moscow").strip()

    if not bot_token:
        raise RuntimeError("BOT_TOKEN is required")
    if not openrouter_api_keys:
        raise RuntimeError("At least one OpenRouter API key is required")

    return Config(
        bot_token=bot_token,
        openrouter_api_keys=openrouter_api_keys,
        openrouter_http_referer=openrouter_http_referer,
        openrouter_app_title=openrouter_app_title,
        admin_ids=_parse_admin_ids(admin_ids_raw),
        sqlite_path=sqlite_path,
        timezone=timezone,
    )
