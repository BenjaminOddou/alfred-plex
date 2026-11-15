"""Parse what the user types in Plex Search.

* ``matrix``                    → hub search on every server
* ``matrix/movie``              → hub search restricted to one media type
* ``lt=movie/de=1980/ct=france``→ library filters (aliases or long names)
* ``AC/DC``                     → plain text, ``/DC`` is not a media type
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .settings import parse_literal
from .store import Alias

HUB_TYPES = {
    "actor", "album", "artist", "autotag", "clip", "collection", "director", "episode", "game",
    "genre", "movie", "photo", "photoalbum", "place", "playlist", "shared", "show", "tag", "track",
}
# Keys handled by the workflow itself, never sent to plexapi.
WORKFLOW_KEYS = {"server", "section", "watchlist"}
# A "/" only starts a new filter when it is followed by "key=".
FILTER_SPLIT = re.compile(r"/(?=\s*[A-Za-z_][\w.]*\s*=)")
# Which library sections can answer a given libtype.
SECTION_TYPES = {
    "movie": {"movie"},
    "show": {"show"}, "season": {"show"}, "episode": {"show"},
    "artist": {"artist"}, "album": {"artist"}, "track": {"artist"},
    "photo": {"photo"}, "photoalbum": {"photo"},
}


class FilterError(ValueError):
    """The query contains an unknown filter or an invalid value."""


@dataclass
class SearchQuery:
    text: str = ""
    mediatype: str | None = None
    filters: dict[str, Any] = field(default_factory=dict)
    advanced: dict | None = None
    servers: set[str] = field(default_factory=set)
    sections: set[str] = field(default_factory=set)
    watchlist: int | None = None

    @property
    def is_filter(self) -> bool:
        return bool(self.filters or self.advanced)

    @property
    def libtype(self) -> str | None:
        value = self.filters.get("libtype")
        return str(value) if value else None

    def accepts_server(self, name: str) -> bool:
        return not self.servers or name.lower() in self.servers

    def accepts_section(self, title: str, section_type: str) -> bool:
        if self.sections and title.lower() not in self.sections:
            return False
        allowed = SECTION_TYPES.get(self.libtype or "")
        return allowed is None or section_type in allowed

    def search_kwargs(self, limit: int) -> dict[str, Any]:
        kwargs = dict(self.filters)
        kwargs["maxresults"] = limit
        if self.advanced:
            kwargs["filters"] = self.advanced
        return kwargs


def _value(text: str) -> Any:
    text = text.strip()
    return int(text) if re.fullmatch(r"-?\d+", text) else text


def _names(value: Any) -> set[str]:
    return {v.strip().lower() for v in str(value).split(",") if v.strip()}


def parse(query: str, alias: Alias) -> SearchQuery:
    query = (query or "").strip()
    if "=" not in query:
        text, _, mediatype = query.rpartition("/")
        if text and mediatype.strip().lower() in HUB_TYPES:
            return SearchQuery(text=text.strip(), mediatype=mediatype.strip().lower())
        return SearchQuery(text=query)

    result = SearchQuery()
    for chunk in FILTER_SPLIT.split(query):
        if not chunk.strip():
            continue
        if "=" not in chunk:
            raise FilterError(f"'{chunk}' is not a filter (expected name=value)")
        key, raw = chunk.split("=", 1)
        name = alias.resolve(key)
        if not name:
            raise FilterError(f"Unknown filter '{key.strip()}'")
        if name == "advancedFilters":
            try:
                value = parse_literal(raw)
            except (ValueError, SyntaxError) as error:
                raise FilterError(f"advancedFilters must be a dict: {error}") from error
            if not isinstance(value, dict):
                raise FilterError("advancedFilters must be a dict")
            result.advanced = value
        elif name == "server":
            result.servers = _names(raw)
        elif name == "section":
            result.sections = _names(raw)
        elif name == "watchlist":
            result.watchlist = 1 if str(raw).strip().lower() in {"1", "true", "yes"} else 0
        else:
            result.filters[name] = _value(raw)
    return result


def default_view(view: dict) -> SearchQuery:
    """SearchQuery for the "👀 Default view" setting (empty query)."""
    result = SearchQuery()
    for key, value in (view or {}).items():
        if key == "server":
            result.servers = _names(value)
        elif key == "section":
            result.sections = _names(value)
        elif key == "watchlist":
            result.watchlist = int(bool(value))
        elif key == "advancedFilters" and isinstance(value, dict):
            result.advanced = value
        else:
            result.filters[key] = value
    return result


def to_text(alias: Alias, pairs: list[tuple[str, Any]]) -> str:
    """Build a filter query such as ``lt=movie/ge=12`` with the right names."""
    return "/".join(f"{alias.display(key)}={value}" for key, value in pairs)
