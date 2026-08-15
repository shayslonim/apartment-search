"""Configuration loading for Apartment Search."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import Criteria


class ConfigError(ValueError):
    """Raised when the watcher configuration is invalid."""


@dataclass(frozen=True)
class SourceConfig:
    """Configuration for one post source."""

    name: str
    type: str
    url: Optional[str] = None
    path: Optional[str] = None


@dataclass(frozen=True)
class ScoringConfig:
    """Configuration for local and OpenAI scoring."""

    use_openai: bool = False
    openai_model: str = "gpt-5-mini"


@dataclass(frozen=True)
class TelegramConfig:
    """Telegram delivery settings."""

    enabled: bool = False
    bot_token_env: str = "TELEGRAM_BOT_TOKEN"
    chat_id_env: str = "TELEGRAM_CHAT_ID"


@dataclass(frozen=True)
class StorageConfig:
    """Seen-post storage settings."""

    path: str = ".apartment-search/seen.sqlite3"


@dataclass(frozen=True)
class FacebookConfig:
    """Playwright browser scraping settings."""

    browser_profile_dir: str = ".apartment-search/browser-profile"
    headless: bool = False
    scrolls: int = 4
    wait_seconds: int = 3
    wait_for_login: bool = False


@dataclass(frozen=True)
class AppConfig:
    """Application configuration."""

    sources: List[SourceConfig] = field(default_factory=list)
    criteria: Criteria = field(default_factory=Criteria)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    facebook: FacebookConfig = field(default_factory=FacebookConfig)
    base_dir: Path = Path(".")


def default_config() -> Dict[str, Any]:
    """Return a serializable default configuration."""

    return {
        "sources": [
            {"name": "sample-posts", "type": "json", "path": "sample_posts.json"}
        ],
        "criteria": {
            "work_address": "HaHaskala 3, Tel Aviv",
            "preferred_areas": ["Montefiore", "Sarona", "HaHaskala 3"],
            "max_shared_price_ils": 4000,
            "stretch_shared_price_ils": 4500,
            "max_solo_price_ils": 4500,
            "move_in_months": ["September 2026", "October 2026"],
            "minimum_score": 70,
        },
        "scoring": {"use_openai": False, "openai_model": "gpt-5-mini"},
        "telegram": {
            "enabled": False,
            "bot_token_env": "TELEGRAM_BOT_TOKEN",
            "chat_id_env": "TELEGRAM_CHAT_ID",
        },
        "storage": {"path": ".apartment-search/seen.sqlite3"},
        "facebook": {
            "browser_profile_dir": ".apartment-search/browser-profile",
            "headless": False,
            "scrolls": 4,
            "wait_seconds": 3,
            "wait_for_login": False,
        },
    }


def write_default_config(path: Path, force: bool = False) -> None:
    """Write a starter config file."""

    if path.exists() and not force:
        raise ConfigError(f"{path} already exists; pass --force to overwrite it")
    path.write_text(
        json.dumps(default_config(), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def load_config(path: Path) -> AppConfig:
    """Load and validate a JSON config file."""

    if not path.exists():
        raise ConfigError(f"Config file does not exist: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError("Config must be a JSON object")

    sources = _load_sources(data.get("sources", []))
    if not sources:
        raise ConfigError("Config must include at least one source")

    criteria = Criteria(
        **_merged_section(default_config()["criteria"], data, "criteria")
    )
    scoring = ScoringConfig(
        **_merged_section(default_config()["scoring"], data, "scoring")
    )
    telegram = TelegramConfig(
        **_merged_section(default_config()["telegram"], data, "telegram")
    )
    storage = StorageConfig(
        **_merged_section(default_config()["storage"], data, "storage")
    )
    facebook = FacebookConfig(
        **_merged_section(default_config()["facebook"], data, "facebook")
    )
    return AppConfig(
        sources=sources,
        criteria=criteria,
        scoring=scoring,
        telegram=telegram,
        storage=storage,
        facebook=facebook,
        base_dir=path.parent,
    )


def resolve_config_path(path: str) -> Path:
    """Resolve a user-provided config path."""

    return Path(path).expanduser().resolve()


def resolve_relative(base_dir: Path, value: str) -> Path:
    """Resolve a path relative to the config file."""

    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def _merged_section(
    defaults: Dict[str, Any], root: Dict[str, Any], section: str
) -> Dict[str, Any]:
    value = root.get(section, {})
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ConfigError(f"{section} must be a JSON object")
    merged = dict(defaults)
    merged.update(value)
    return merged


def _load_sources(raw_sources: Any) -> List[SourceConfig]:
    if not isinstance(raw_sources, list):
        raise ConfigError("sources must be a list")

    sources: List[SourceConfig] = []
    for index, raw in enumerate(raw_sources):
        if not isinstance(raw, dict):
            raise ConfigError(f"sources[{index}] must be an object")
        name = raw.get("name")
        source_type = raw.get("type")
        if not name or not isinstance(name, str):
            raise ConfigError(f"sources[{index}].name is required")
        if source_type not in {"json", "facebook_browser"}:
            raise ConfigError(
                f"sources[{index}].type must be 'json' or 'facebook_browser'"
            )
        source = SourceConfig(
            name=name,
            type=source_type,
            url=_optional_str(raw.get("url")),
            path=_optional_str(raw.get("path")),
        )
        if source.type == "json" and not source.path:
            raise ConfigError(f"sources[{index}].path is required for json sources")
        if source.type == "facebook_browser" and not source.url:
            raise ConfigError(
                f"sources[{index}].url is required for facebook_browser sources"
            )
        sources.append(source)
    return sources


def _optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError("Expected a string value")
    return value
