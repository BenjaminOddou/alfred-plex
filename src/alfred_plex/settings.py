"""Workflow settings, read once from the environment Alfred gives us."""

from __future__ import annotations

import ast
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from . import BUNDLE_ID

WORKFLOW_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = f"~/Library/Application Support/Alfred/Workflow Data/{BUNDLE_ID}"
DEFAULT_CACHE_DIR = f"~/Library/Caches/com.runningwithcrayons.Alfred/Workflow Data/{BUNDLE_ID}"
DISABLED = {"", "false", "none", "0", "off"}
MEDIA_PLAYERS = ("vlc", "iina", "infuse")
# How Plex Search / Plex Discover show their results (``search_view`` setting).
SEARCH_VIEWS = ("list", "list_posters", "grid")
# What → then ↩ on "Plex" (Alfred's actions panel) does on a media (``right_arrow`` setting).
RIGHT_ARROW_ACTIONS = ("sheet", "more", "actions", "play", "web")


def _text(env: Mapping[str, str], key: str, default: str) -> str:
    value = env.get(key)
    return value.strip() if value and value.strip() else default


def _int(env: Mapping[str, str], key: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(env.get(key, default)))
    except (TypeError, ValueError):
        return default


def _bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    value = env.get(key)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _shortcut(env: Mapping[str, str], key: str, default: str) -> str:
    """Return a modifier key ("cmd", "alt+shift"...), "arg" for ⏎ or "" when disabled."""
    value = env.get(key, default)
    return "" if value is None or value.strip().lower() in DISABLED else value.strip()


def _choice(env: Mapping[str, str], key: str, choices: tuple[str, ...]) -> str:
    """One of ``choices`` (the first one is the default)."""
    value = _text(env, key, choices[0]).lower()
    return value if value in choices else choices[0]


def parse_literal(text: str):
    """Parse a Python literal or JSON text without ever running code."""
    text = (text or "").strip()
    if not text:
        raise ValueError("empty value")
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return json.loads(text)


def _default_view(env: Mapping[str, str]) -> dict:
    raw = env.get("default_view")
    if raw is None:
        return {"sort": "originallyAvailableAt:desc"}
    try:
        value = parse_literal(raw)
    except (ValueError, SyntaxError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


@dataclass(frozen=True)
class Shortcuts:
    """Which key triggers each media action ("" = disabled, "arg" = ⏎).

    When ⏎ is left free for a media (e.g. a movie has no nested search),
    it opens the media actions page, so every row always does something.
    """

    nested_search: str = "arg"
    web: str = "cmd"
    stream: str = "alt"
    mtv: str = "ctrl"
    watchlist: str = "shift"
    actions: str = "fn"
    played: str = "cmd+shift"
    download: str = ""

    # (setting variable, field, default, label) – used by the config and the shortcuts page
    FIELDS = (
        ("short_actions", "actions", "fn", "Media actions page"),
        ("short_nested_search", "nested_search", "arg", "Nested search"),
        ("short_web", "web", "cmd", "Open on the web"),
        ("short_stream", "stream", "alt", "Stream locally"),
        ("short_mtvsearch", "mtv", "ctrl", "Movie and TV Show Search"),
        ("short_watchlist", "watchlist", "shift", "Add / remove watchlist"),
        ("short_played", "played", "cmd+shift", "Mark played / unplayed"),
        ("short_download", "download", "", "Download the file"),
    )


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    cache_dir: Path
    downloads_dir: Path
    workflow_dir: Path = WORKFLOW_DIR
    version: str = ""
    language: str = "en"
    notify: bool = True  # 🔔 Notifications checkbox
    sound: str = "Submarine"
    log_level: str = "INFO"
    date_format: str = "%Y-%m-%d"
    use_alias: bool = True
    default_view: dict = field(default_factory=dict)
    limit: int = 15
    history_days: int = 15
    stale_days: int = 90
    grid_columns: int = 5
    media_player: str = "vlc"
    search_view: str = "list"
    right_arrow: str = "sheet"
    shortcuts: Shortcuts = field(default_factory=Shortcuts)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env
        player = _text(env, "media_player", "vlc").lower()
        return cls(
            data_dir=Path(_text(env, "data_folder", DEFAULT_DATA_DIR)).expanduser(),
            cache_dir=Path(
                _text(env, "alfred_workflow_cache", DEFAULT_CACHE_DIR)
            ).expanduser(),
            downloads_dir=Path(_text(env, "downloads_folder", "~/Downloads")).expanduser(),
            version=env.get("alfred_workflow_version", ""),
            language=_text(env, "language", "en"),
            notify=_bool(env, "notify", True),
            # An empty sound means "mute", so it must not fall back to the default.
            sound=env.get("sound", "Submarine"),
            log_level=_text(env, "log_level", "INFO").upper(),
            date_format=_text(env, "date_format", "%Y-%m-%d"),
            use_alias=_bool(env, "filters_bool", True),
            default_view=_default_view(env),
            limit=_int(env, "limit_number", 15),
            history_days=_int(env, "days_history", 15),
            stale_days=_int(env, "days_devices", 90),
            grid_columns=min(10, _int(env, "grid_columns", 5, minimum=2)),
            media_player=player if player in MEDIA_PLAYERS else "vlc",
            search_view=_choice(env, "search_view", SEARCH_VIEWS),
            right_arrow=_choice(env, "right_arrow", RIGHT_ARROW_ACTIONS),
            shortcuts=Shortcuts(**{
                name: _shortcut(env, variable, default) for variable, name, default, _ in Shortcuts.FIELDS
            }),
        )

    @property
    def list_posters(self) -> bool:
        """Lists show posters as icons (downloaded in the cache): "List with posters" and "Grid" views."""
        return self.search_view in {"list_posters", "grid"}

    @property
    def grid_view(self) -> bool:
        """Plex Search / Discover results open in the Grid View."""
        return self.search_view == "grid"

    def ensure_dirs(self) -> None:
        for folder in (self.data_dir, self.cache_dir):
            folder.mkdir(parents=True, exist_ok=True)
