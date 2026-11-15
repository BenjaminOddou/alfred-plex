"""Statistics computed from plexapi objects (pure functions, no Alfred here).

The same functions feed the statistics pages and the CSV exports, so what
you see in Alfred is what you get in the file.
"""

from __future__ import annotations

import contextlib
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
SUBTYPES = {"show": ("season", "episode"), "artist": ("album", "track")}


@dataclass
class Lookups:
    """Names of the ids found in history / bandwidth data (one request each, cached by plexapi)."""

    accounts: dict[int, str] = field(default_factory=dict)
    devices: dict[int, str] = field(default_factory=dict)
    platforms: dict[int, str] = field(default_factory=dict)
    sections: dict[int, str] = field(default_factory=dict)

    @classmethod
    def from_server(cls, plex: Any) -> Lookups:
        devices = plex.systemDevices()
        return cls(
            accounts={a.id: a.name or f"Account {a.id}" for a in plex.systemAccounts()},
            devices={d.id: d.name or f"Device {d.id}" for d in devices},
            platforms={d.id: d.platform or "Unknown" for d in devices},
            sections={s.key: s.title for s in plex.library.sections()},
        )

    def account(self, account_id: int | None) -> str:
        return self.accounts.get(account_id, "Unknown user") if account_id is not None else "Unknown user"

    def device(self, device_id: int | None) -> str:
        return self.devices.get(device_id, "Unknown device") if device_id is not None else "Unknown device"

    def platform(self, device_id: int | None) -> str:
        return self.platforms.get(device_id, "Unknown") if device_id is not None else "Unknown"

    def section(self, section_id: int | None) -> str:
        return self.sections.get(section_id, "Deleted Library") if section_id is not None else "Deleted Library"


def media_label(entry: Any) -> str:
    """Title used to rank what is watched: episodes count for their show, tracks for their artist."""
    kind = getattr(entry, "type", None)
    if kind in {"episode", "track"} and getattr(entry, "grandparentTitle", None):
        return entry.grandparentTitle
    year = getattr(entry, "year", None)
    return f"{entry.title} ({year})" if year else str(entry.title)


@dataclass
class Plays:
    total: int = 0
    users: Counter = field(default_factory=Counter)
    devices: Counter = field(default_factory=Counter)
    platforms: Counter = field(default_factory=Counter)
    libraries: Counter = field(default_factory=Counter)
    titles: Counter = field(default_factory=Counter)
    types: Counter = field(default_factory=Counter)
    weekdays: Counter = field(default_factory=Counter)
    hours: Counter = field(default_factory=Counter)
    days: Counter = field(default_factory=Counter)


def plays(entries: Iterable[Any], names: Lookups) -> Plays:
    result = Plays()
    for entry in entries:
        result.total += 1
        result.users[names.account(entry.accountID)] += 1
        result.devices[names.device(entry.deviceID)] += 1
        result.platforms[names.platform(entry.deviceID)] += 1
        result.libraries[names.section(entry.librarySectionID)] += 1
        result.titles[media_label(entry)] += 1
        result.types[entry.type or "other"] += 1
        if entry.viewedAt:
            result.weekdays[WEEKDAYS[entry.viewedAt.weekday()]] += 1
            result.hours[entry.viewedAt.hour] += 1
            result.days[entry.viewedAt.date()] += 1
    return result


@dataclass
class Bandwidth:
    total: int = 0
    lan: int = 0
    days: dict[date, list[int]] = field(default_factory=lambda: defaultdict(lambda: [0, 0]))  # [lan, wan]
    users: Counter = field(default_factory=Counter)
    devices: Counter = field(default_factory=Counter)

    @property
    def wan(self) -> int:
        return self.total - self.lan


def bandwidth(samples: Iterable[Any], names: Lookups) -> Bandwidth:
    result = Bandwidth()
    for sample in samples:
        size = sample.bytes or 0
        result.total += size
        if sample.lan:
            result.lan += size
        if sample.at:
            result.days[sample.at.date()][0 if sample.lan else 1] += size
        result.users[names.account(sample.accountID)] += size
        result.devices[names.device(sample.deviceID)] += size
    return result


def storage_map(plex: Any) -> dict[int, tuple[int, int]]:
    """{section key: (duration ms, size bytes)} in one request.

    Parsed here because plexapi's ``totalStorage`` tests an XML element for
    truthiness, which is False for elements without children.
    """
    data = plex.query("/media/providers?includeStorage=1")
    totals = {}
    for feature in data.iter("Feature"):
        if feature.attrib.get("type") != "content":
            continue
        for directory in feature.iter("Directory"):
            key = directory.attrib.get("id", "")
            if key.isdigit():
                totals[int(key)] = (int(directory.attrib.get("durationTotal") or 0),
                                    int(directory.attrib.get("storageTotal") or 0))
    return totals


def library_rows(sections: Iterable[Any], totals: dict[int, tuple[int, int]] | None = None) -> list[dict]:
    """One row per library section: counts per type, size and duration."""
    rows = []
    for section in sections:
        counts = {section.type: section.totalViewSize(libtype=section.type, includeCollections=False)}
        for subtype in SUBTYPES.get(section.type, ()):
            counts[subtype] = section.totalViewSize(libtype=subtype, includeCollections=False)
        rows.append({
            "section": section.title,
            "type": section.type,
            "counts": counts,
            "size": (totals or {}).get(section.key, (0, 0))[1],
            "duration": (totals or {}).get(section.key, (0, 0))[0],
        })
    return rows


def count(section: Any, libtype: str, **filters: Any) -> int:
    """Number of items matching ``filters`` without downloading them (container size 0)."""
    key = section._buildSearchKey(libtype=libtype, **filters)
    sep = "&" if "?" in key else "?"
    data = section._server.query(f"{key}{sep}X-Plex-Container-Start=0&X-Plex-Container-Size=0")
    return int(data.attrib.get("totalSize") or data.attrib.get("size") or 0)


QUALITY_TYPES = {"movie": "movie", "show": "episode"}


def quality(section: Any) -> dict[str, int]:
    """Items per video resolution (+ HDR) of a movie / TV section."""
    libtype = QUALITY_TYPES.get(section.type)
    if not libtype:
        return {}
    result = {}
    for choice in section.listFilterChoices("resolution", libtype=libtype):
        result[choice.title] = count(section, libtype, resolution=choice.key)
    with contextlib.suppress(Exception):  # old servers have no HDR filter
        result["HDR"] = count(section, libtype, hdr=1)
    return result


def top(counter: Counter, limit: int = 5) -> list[tuple[Any, int]]:
    return counter.most_common(limit)
