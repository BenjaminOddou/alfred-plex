"""JSON files of the data folder (accounts, servers, presets, alias).

File formats are unchanged from v2, so existing user data keeps working.
Writes are atomic (temp file + rename): a crash never leaves half a file.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .settings import Settings

log = logging.getLogger("alfred_plex")


def read_json(path: Path, default: Any) -> Any:
    try:
        with path.open(encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return default
    except (OSError, ValueError) as error:
        log.warning("Cannot read %s: %s", path, error)
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class ItemsFile:
    """A ``{"items": [...]}`` JSON file with a primary key."""

    def __init__(self, path: Path, key: str, seed: Path | None = None) -> None:
        self.path = path
        self.key = key
        self.seed = seed
        self._items: list[dict] | None = None

    @property
    def items(self) -> list[dict]:
        if self._items is None:
            if self.seed and not self.path.exists():
                shutil.copyfile(self.seed, self.path)
            data = read_json(self.path, {"items": []})
            items = data.get("items") if isinstance(data, dict) else None
            self._items = [i for i in items or [] if isinstance(i, dict)]
        return self._items

    def get(self, value: str) -> dict | None:
        return next((i for i in self.items if i.get(self.key) == value), None)

    def upsert(self, item: dict) -> bool:
        """Insert or replace ``item``. Returns True when it was an update."""
        for index, current in enumerate(self.items):
            if current.get(self.key) == item.get(self.key):
                self.items[index] = item
                return True
        self.items.append(item)
        return False

    def remove(self, value: str, field: str | None = None) -> list[dict]:
        field = field or self.key
        removed = [i for i in self.items if i.get(field) == value]
        self._items = [i for i in self.items if i.get(field) != value]
        return removed

    def save(self) -> None:
        write_json(self.path, {"items": self.items})


@dataclass
class AliasEntry:
    short: str
    long: str


class Alias:
    """Filter aliases: ``lt`` ⇄ ``libtype``, ``af`` ⇄ ``advancedFilters``...

    Both the alias and the long name are always accepted when parsing,
    ``enabled`` only changes what the workflow *displays*.
    """

    def __init__(self, entries: list[AliasEntry], enabled: bool) -> None:
        self.entries = entries
        self.enabled = enabled
        self._to_long = {e.short: e.long for e in entries}
        self._to_short = {e.long: e.short for e in entries}

    def resolve(self, key: str) -> str | None:
        """Long filter name for ``key`` (alias or long name), None if unknown."""
        key = key.strip()
        if key in self._to_long:
            return self._to_long[key]
        if key in self._to_short:
            return key
        return None

    def short(self, long_key: str) -> str | None:
        return self._to_short.get(long_key)

    def display(self, long_key: str) -> str:
        """Name shown to the user for a filter (alias when alias mode is on)."""
        if self.enabled:
            return self._to_short.get(long_key, long_key)
        return long_key

    def to_json(self) -> list[dict]:
        return [{"short_key": e.short, "long_key": e.long} for e in self.entries]


class Store:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        data, bundled = settings.data_dir, settings.workflow_dir / "json"
        self.accounts = ItemsFile(data / "accounts.json", "uuid")
        self.servers = ItemsFile(data / "servers.json", "machineIdentifier")
        self.presets = ItemsFile(data / "presets.json", "id", seed=bundled / "presets.json")
        self.alias_path = data / "alias.json"
        self.bundled_alias_path = bundled / "alias.json"
        self._alias: Alias | None = None

    # ------------------------------------------------------------ alias
    def _alias_entries(self, path: Path) -> list[AliasEntry]:
        raw = read_json(path, [])
        if not isinstance(raw, list):
            return []
        return [
            AliasEntry(str(e["short_key"]), str(e["long_key"]))
            for e in raw
            if isinstance(e, dict) and e.get("short_key") and e.get("long_key")
        ]

    @property
    def alias(self) -> Alias:
        if self._alias is None:
            defaults = self._alias_entries(self.bundled_alias_path)
            entries = self._alias_entries(self.alias_path) if self.alias_path.exists() else []
            known_long = {e.long for e in entries}
            known_short = {e.short for e in entries}
            # New filters shipped with an update are merged into the user's file.
            missing = [e for e in defaults if e.long not in known_long and e.short not in known_short]
            if missing or not entries:
                entries = entries + missing
                write_json(self.alias_path, [{"short_key": e.short, "long_key": e.long} for e in entries])
            self._alias = Alias(entries, self.settings.use_alias)
        return self._alias

    def save_alias(self, alias: Alias) -> None:
        write_json(self.alias_path, alias.to_json())
        self._alias = alias

    def reset_alias(self) -> None:
        shutil.copyfile(self.bundled_alias_path, self.alias_path)
        self._alias = None

    # ---------------------------------------------------------- helpers
    def server(self, machine_id: str) -> dict | None:
        return self.servers.get(machine_id)

    def account(self, uuid: str) -> dict | None:
        return self.accounts.get(uuid)

    @staticmethod
    def new_id() -> str:
        return secrets.token_hex(16)
