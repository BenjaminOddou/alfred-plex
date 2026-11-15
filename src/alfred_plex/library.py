"""Library browser state: sort and filters picked from lists, no syntax to learn.

The state travels in the ``state`` Alfred variable as JSON::

    {"sort": "addedAt:desc", "filters": {"genre": "12", "unwatched": 1},
     "labels": {"genre": "Action", "unwatched": "Unplayed"}, "view": "grid"}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import stats
from .filters import to_text
from .store import Alias

DEFAULT_SORT = "addedAt:desc"
BOOLEAN = "boolean"


@dataclass
class LibraryState:
    sort: str = DEFAULT_SORT
    filters: dict[str, Any] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    view: str = "list"

    @classmethod
    def from_dict(cls, data: dict | None) -> LibraryState:
        data = data or {}
        return cls(
            sort=str(data.get("sort") or DEFAULT_SORT),
            filters=dict(data.get("filters") or {}),
            labels={k: str(v) for k, v in (data.get("labels") or {}).items()},
            view="grid" if data.get("view") == "grid" else "list",
        )

    def to_dict(self) -> dict:
        data: dict[str, Any] = {"sort": self.sort, "view": self.view}
        if self.filters:
            data["filters"] = self.filters
            data["labels"] = self.labels
        return data

    # ---------------------------------------------------------- changes
    def replace(self, **changes: Any) -> LibraryState:
        data = {"sort": self.sort, "filters": dict(self.filters), "labels": dict(self.labels), "view": self.view}
        data.update(changes)
        return LibraryState(**data)

    def with_filter(self, name: str, value: Any, label: str) -> LibraryState:
        return self.replace(filters={**self.filters, name: value}, labels={**self.labels, name: label})

    def without(self, name: str) -> LibraryState:
        return self.replace(filters={k: v for k, v in self.filters.items() if k != name},
                            labels={k: v for k, v in self.labels.items() if k != name})

    def cleared(self) -> LibraryState:
        return self.replace(filters={}, labels={})

    # ----------------------------------------------------------- display
    @property
    def sort_field(self) -> str:
        return self.sort.split(":", 1)[0]

    @property
    def descending(self) -> bool:
        return self.sort.endswith(":desc")

    def sort_label(self, titles: dict[str, str] | None = None) -> str:
        name = (titles or {}).get(self.sort_field, self.sort_field)
        return f"{name} {'↓' if self.descending else '↑'}"

    def filters_label(self) -> str:
        if not self.filters:
            return "none"
        return " · ".join(self.labels.get(name, f"{name}={value}") for name, value in self.filters.items())


def libtype(section: Any) -> str:
    return section.TYPE


def results(section: Any, state: LibraryState, maxresults: int) -> list[Any]:
    return section.search(libtype=libtype(section), sort=state.sort, maxresults=maxresults, **state.filters)


def total(section: Any, state: LibraryState) -> int:
    return stats.count(section, libtype(section), **state.filters)


def search_text(alias: Alias, section: Any, state: LibraryState) -> str:
    """Same browse as a Plex Search query (to tweak it by hand or save it as a preset)."""
    pairs: list[tuple[str, Any]] = [("section", section.title), ("libtype", libtype(section))]
    pairs += list(state.filters.items())
    pairs.append(("sort", state.sort))
    return to_text(alias, pairs)


def filter_label(filter_title: str, choice_title: str, filter_type: str) -> str:
    return filter_title if filter_type == BOOLEAN else f"{filter_title}: {choice_title}"
