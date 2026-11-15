"""Everything that talks to python-plexapi: config, connections and caches.

plexapi is imported lazily so that pages which do not need it (menu,
presets, help...) open instantly.
"""

from __future__ import annotations

import json
import logging
import os
import pickle
import platform
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

from .settings import Settings
from .store import read_json, write_json

if TYPE_CHECKING:  # pragma: no cover
    from plexapi.myplex import MyPlexAccount
    from plexapi.server import PlexServer

log = logging.getLogger("alfred_plex")

T = TypeVar("T")
R = TypeVar("R")

ACCOUNT_TTL = 24 * 3600  # a cached account is refreshed once a day
WATCHLIST_TTL = 10 * 60
CONNECT_TIMEOUT = 5


class PlexError(Exception):
    """Error with a message that can be shown to the user as is."""


# ------------------------------------------------------------------ setup
def plexapi_config(settings: Settings) -> str:
    return "\n".join(
        [
            "[plexapi]",
            f"timeout = {CONNECT_TIMEOUT}",
            "autoreload = false",
            "enable_fast_connect = true",
            "",
            "[header]",
            "device = OSX",
            "device_name = Alfred Plex",
            f"language = {settings.language}",
            "platform = macOS",
            f"platform_version = {platform.mac_ver()[0]}",
            "product = Alfred Workflow",
            "provides = controller",
            f"version = {settings.version}",
            "",
        ]
    )


def bootstrap(settings: Settings) -> None:
    """Write plexapi's config (only when it changed) and point plexapi to it.

    Must run before the first ``import plexapi``. When the workflow version
    changes, cached objects are dropped (user data is kept).
    """
    settings.ensure_dirs()
    config = settings.cache_dir / "plexapi.ini"
    content = plexapi_config(settings)
    if not config.exists() or config.read_text(encoding="utf-8") != content:
        config.write_text(content, encoding="utf-8")
    os.environ["PLEXAPI_CONFIG_PATH"] = str(config)

    marker = settings.cache_dir / "version"
    previous = marker.read_text(encoding="utf-8").strip() if marker.exists() else None
    if previous != settings.version:
        for path in settings.cache_dir.iterdir():
            if path.is_file() and (path.suffix in {".pickle", ".json"} or "." not in path.name):
                path.unlink(missing_ok=True)
        (settings.data_dir / "config.ini").unlink(missing_ok=True)  # v2 leftover
        marker.write_text(settings.version, encoding="utf-8")


# -------------------------------------------------------------- parallel
def parallel(func: Callable[[T], R], items: Iterable[T], workers: int = 8) -> list[R | Exception]:
    """Run ``func`` on every item in threads. Errors are returned, not raised."""
    items = list(items)

    def safe(item: T) -> R | Exception:
        try:
            return func(item)
        except Exception as error:  # noqa: BLE001 - reported to the caller
            log.warning("%s failed for %r: %r", getattr(func, "__name__", "task"), item, error)
            return error

    if len(items) <= 1:
        return [safe(i) for i in items]
    with ThreadPoolExecutor(max_workers=min(workers, len(items))) as pool:
        return list(pool.map(safe, items))


# ---------------------------------------------------------------- server
def connect(server: dict) -> PlexServer:
    from plexapi.server import PlexServer

    return PlexServer(server["baseURL"], server["plexToken"], timeout=CONNECT_TIMEOUT)


# --------------------------------------------------------------- account
def _account_cache(settings: Settings, uuid: str) -> Path:
    return settings.cache_dir / f"account-{uuid}.pickle"


def cache_account(settings: Settings, account: MyPlexAccount) -> None:
    try:
        with _account_cache(settings, account.uuid).open("wb") as file:
            pickle.dump(account, file)
    except (OSError, pickle.PicklingError, AttributeError, TypeError) as error:
        log.warning("Cannot cache account: %r", error)


def forget_account(settings: Settings, uuid: str) -> None:
    _account_cache(settings, uuid).unlink(missing_ok=True)
    _watchlist_cache(settings, uuid).unlink(missing_ok=True)


def sign_in(token: str) -> MyPlexAccount:
    """Account from an OAuth token (the only sign in method since 3.1)."""
    from plexapi.myplex import MyPlexAccount

    return MyPlexAccount(token=token)


def load_account(settings: Settings, token: str, uuid: str, fresh: bool = False) -> MyPlexAccount:
    """Account from the cache (no network) or from plex.tv when stale.

    v2 checked the cached account with an extra ``users()`` call on every
    keystroke; now a bad token simply surfaces on the real request.
    """
    path = _account_cache(settings, uuid)
    if not fresh and path.exists() and time.time() - path.stat().st_mtime < ACCOUNT_TTL:
        try:
            with path.open("rb") as file:
                return pickle.load(file)
        except Exception as error:  # noqa: BLE001 - corrupted cache, rebuild it
            log.warning("Ignoring account cache: %r", error)
    account = sign_in(token=token)
    cache_account(settings, account)
    return account


# ------------------------------------------------------------- watchlist
def _watchlist_cache(settings: Settings, uuid: str) -> Path:
    return settings.cache_dir / f"watchlist-{uuid}.json"


def watchlist_guids(settings: Settings, uuid: str, get_account: Callable[[], MyPlexAccount]) -> set[str]:
    """GUIDs of the account watchlist, cached for a few minutes."""
    path = _watchlist_cache(settings, uuid)
    data = read_json(path, {})
    if isinstance(data, dict) and time.time() - data.get("time", 0) < WATCHLIST_TTL:
        return set(data.get("guids", []))
    guids = {item.guid for item in get_account().watchlist()}
    write_json(path, {"time": time.time(), "guids": sorted(guids)})
    return guids


def update_watchlist_cache(settings: Settings, uuid: str, guid: str, add: bool) -> None:
    path = _watchlist_cache(settings, uuid)
    data = read_json(path, None)
    if not isinstance(data, dict):
        return
    guids = set(data.get("guids", []))
    guids.add(guid) if add else guids.discard(guid)
    data["guids"] = sorted(guids)
    write_json(path, data)


def online_guids(account: MyPlexAccount, rating_key: str) -> list[str]:
    """External ids (imdb://, tmdb://, tvdb://) of a Discover item."""
    data = account.query(f"{account.METADATA}/library/metadata/{rating_key}")
    return [guid.attrib.get("id", "") for guid in data.iter("Guid")]


def discover_json(account: MyPlexAccount, path: str, **params) -> dict:
    """GET a Discover endpoint as JSON, with the account token and plexapi headers."""
    data = account.query(f"{account.DISCOVER}{path}", headers={"Accept": "application/json"}, params=params)
    if isinstance(data, (bytes, str)):
        data = json.loads(data)
    return data if isinstance(data, dict) else {}
