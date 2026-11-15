"""Per-run context shared by pages and commands."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING

from . import plex
from .alfred import Intent
from .settings import Settings
from .store import Store

if TYPE_CHECKING:  # pragma: no cover
    from plexapi.myplex import MyPlexAccount
    from plexapi.server import PlexServer


@dataclass
class Context:
    settings: Settings
    store: Store
    query: str = ""
    env: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))
    nav: str = ""
    _servers: dict = field(default_factory=dict, repr=False)
    _accounts: dict = field(default_factory=dict, repr=False)

    @classmethod
    def create(cls, query: str = "", env: Mapping[str, str] | None = None) -> Context:
        env = dict(os.environ if env is None else env)
        settings = Settings.from_env(env)
        return cls(settings=settings, store=Store(settings), query=query, env=env, nav=env.get("nav", ""))

    # ---------------------------------------------------------- variables
    def var(self, name: str, default: str = "") -> str:
        return self.env.get(name) or default

    @cached_property
    def payload(self) -> dict:
        try:
            data = json.loads(self.var("payload") or "{}")
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    @cached_property
    def state(self) -> dict:
        """Sort / filters of the library browser (``state`` variable)."""
        try:
            data = json.loads(self.var("state") or "{}")
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    @cached_property
    def history(self) -> list[dict]:
        """Pages the user came from (``back`` variable, a JSON stack)."""
        from .alfred import parse_history

        return parse_history(self.var("back"))

    def intent_var(self, name: str) -> Intent | None:
        return Intent.from_json(self.var(name))

    # ---------------------------------------------------------------- plex
    def server(self, machine_id: str) -> PlexServer:
        """Connected PlexServer for a saved server (memoized for this run)."""
        if machine_id not in self._servers:
            saved = self.store.server(machine_id)
            if not saved:
                raise plex.PlexError("This server is not saved in the workflow anymore")
            try:
                self._servers[machine_id] = plex.connect(saved)
            except Exception as error:
                name = saved.get("friendlyName") or saved.get("title")
                raise plex.PlexError(f"Failed to connect to the plex server {name}") from error
        return self._servers[machine_id]

    def account(self, uuid: str, fresh: bool = False) -> MyPlexAccount:
        if fresh or uuid not in self._accounts:
            saved = self.store.account(uuid)
            if not saved or not saved.get("authToken"):
                raise plex.PlexError("This plex account is not connected anymore")
            try:
                self._accounts[uuid] = plex.load_account(self.settings, saved["authToken"], uuid, fresh=fresh)
            except Exception as error:
                raise plex.PlexError(f"Failed to connect to the plex account {saved.get('title', '')}") from error
        return self._accounts[uuid]

    def watchlist(self, uuid: str) -> set[str]:
        try:
            return plex.watchlist_guids(self.settings, uuid, lambda: self.account(uuid))
        except Exception:  # noqa: BLE001 - the watchlist is a nice-to-have
            return set()

    def default_account(self) -> dict | None:
        items = self.store.accounts.items
        return items[0] if items else None
