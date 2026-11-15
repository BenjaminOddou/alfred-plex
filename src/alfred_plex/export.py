"""CSV exports (opened by Numbers / Excel) and workflow logs archive.

Every exporter returns ``(columns, rows)``; :func:`write_csv` adds a
timestamped file in the downloads folder. Files are UTF-8 with BOM so that
accents look right in Excel.
"""

from __future__ import annotations

import csv
import platform
import zipfile
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from . import fmt, stats
from .context import Context
from .plex import parallel

Table = tuple[list[str], list[list[Any]]]
EXPORTERS: dict[str, Callable[[Context, dict], Table]] = {}
LEAF_TYPES = {"movie": "movie", "show": "episode", "artist": "track", "photo": "photo"}


def exporter(kind: str) -> Callable:
    def decorator(func: Callable[[Context, dict], Table]) -> Callable[[Context, dict], Table]:
        EXPORTERS[kind] = func
        return func

    return decorator


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-") or "export"


def write_csv(folder: Path, name: str, columns: list[str], rows: Iterable[Iterable[Any]]) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"plex-{_slug(name)}-{_stamp()}.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        for row in rows:
            writer.writerow(["" if value is None else value for value in row])
    return path


def _date(value: datetime | None, with_time: bool = False) -> str:
    if not value:
        return ""
    return value.strftime("%Y-%m-%d %H:%M" if with_time else "%Y-%m-%d")


def _tags(values: Any) -> str:
    return ", ".join(t.tag for t in values or [] if getattr(t, "tag", None))


def _guid(media: Any, provider: str) -> str:
    for guid in getattr(media, "guids", None) or []:
        if str(guid.id).startswith(f"{provider}://"):
            return guid.id.split("://", 1)[1]
    return ""


# ------------------------------------------------------------------- server
@exporter("library")
def library(ctx: Context, params: dict) -> Table:
    plex = ctx.server(params["mid"])
    section = plex.library.sectionByID(int(params["section"]))
    libtype = LEAF_TYPES.get(section.type, section.type)
    columns = ["title", "show / artist", "season / album", "number", "year", "added", "duration", "views",
               "last viewed", "user rating", "audience rating", "content rating", "studio", "genres",
               "resolution", "video codec", "audio codec", "container", "bitrate (kbps)", "size (bytes)", "size",
               "file", "tmdb", "imdb", "plex guid"]
    rows = []
    for media in section.search(libtype=libtype):
        version = (getattr(media, "media", None) or [None])[0]
        part = version.parts[0] if version is not None and version.parts else None
        rows.append([
            media.title, getattr(media, "grandparentTitle", ""), getattr(media, "parentTitle", ""),
            getattr(media, "index", ""), getattr(media, "year", ""), _date(getattr(media, "addedAt", None)),
            fmt.duration(getattr(media, "duration", None)), getattr(media, "viewCount", 0),
            _date(getattr(media, "lastViewedAt", None)), getattr(media, "userRating", ""),
            getattr(media, "audienceRating", ""), getattr(media, "contentRating", ""), getattr(media, "studio", ""),
            _tags(getattr(media, "genres", None)),
            version and version.videoResolution, version and version.videoCodec, version and version.audioCodec,
            version and version.container, version and version.bitrate, part and part.size,
            fmt.size(part.size) if part and part.size else "", part and part.file,
            _guid(media, "tmdb"), _guid(media, "imdb"), media.guid,
        ])
    return columns, rows


@exporter("history")
def history(ctx: Context, params: dict) -> Table:
    plex = ctx.server(params["mid"])
    since = fmt.since(ctx.settings.history_days)
    section = params.get("section")
    target = plex.library.sectionByID(int(section)) if section not in (None, "") else plex
    names = stats.Lookups.from_server(plex)
    columns = ["date", "user", "device", "platform", "library", "type", "title", "show / artist", "season / album",
               "number"]
    rows = [[
        _date(e.viewedAt, with_time=True), names.account(e.accountID), names.device(e.deviceID),
        names.platform(e.deviceID), names.section(e.librarySectionID), e.type, e.title,
        getattr(e, "grandparentTitle", ""), getattr(e, "parentTitle", ""), getattr(e, "index", ""),
    ] for e in target.history(mindate=since)]
    return columns, rows


@exporter("bandwidth")
def bandwidth(ctx: Context, params: dict) -> Table:
    plex = ctx.server(params["mid"])
    names = stats.Lookups.from_server(plex)
    samples = plex.bandwidth(timespan="days", **{"at>": fmt.since(ctx.settings.history_days)})
    columns = ["date", "user", "device", "network", "bytes", "size"]
    rows = [[_date(s.at), names.account(s.accountID), names.device(s.deviceID), "local" if s.lan else "remote",
             s.bytes, fmt.size(s.bytes)] for s in samples]
    return columns, rows


@exporter("libraries")
def libraries(ctx: Context, params: dict) -> Table:
    plex = ctx.server(params["mid"])
    columns = ["section", "type", "items", "seasons / albums", "episodes / tracks", "size (bytes)", "size",
               "duration (hours)"]
    rows = []
    for row in stats.library_rows(plex.library.sections(), stats.storage_map(plex)):
        counts = list(row["counts"].values()) + ["", ""]
        rows.append([row["section"], row["type"], counts[0], counts[1], counts[2], row["size"], fmt.size(row["size"]),
                     round(row["duration"] / 3_600_000, 1)])
    return columns, rows


@exporter("quality")
def quality(ctx: Context, params: dict) -> Table:
    plex = ctx.server(params["mid"])
    rows = []
    sections = [s for s in plex.library.sections() if s.type in stats.QUALITY_TYPES]
    for section, result in zip(sections, parallel(stats.quality, sections, workers=4), strict=True):
        if not isinstance(result, Exception):  # a broken section must not cancel the whole export
            rows += [[section.title, name, value] for name, value in result.items()]
    return ["section", "resolution", "items"], rows


@exporter("sessions")
def sessions(ctx: Context, params: dict) -> Table:
    from .views.servers import session_quality, session_title

    plex = ctx.server(params["mid"])
    columns = ["title", "user", "player", "device", "platform", "state", "position", "duration", "quality"]
    rows = []
    for s in plex.sessions():
        player = s.player
        rows.append([session_title(s), ", ".join(s.usernames), player and player.product, player and player.device,
                     player and player.platform, player and player.state, fmt.duration(s.viewOffset),
                     fmt.duration(s.duration), session_quality(s)])
    return columns, rows


@exporter("settings")
def settings(ctx: Context, params: dict) -> Table:
    plex = ctx.server(params["mid"])
    columns = ["id", "label", "group", "type", "value", "default", "hidden", "advanced", "summary"]
    rows = [[s.id, s.label, s.group, s.type, s.value, s.default, s.hidden, s.advanced, s.summary]
            for s in plex.settings.all()]
    return columns, rows


# ------------------------------------------------------------------ account
@exporter("watchlist")
def watchlist(ctx: Context, params: dict) -> Table:
    account = ctx.account(params["uuid"])
    columns = ["title", "year", "type", "release date", "duration", "content rating", "studio", "plex guid"]
    rows = [[m.title, m.year, m.type, _date(getattr(m, "originallyAvailableAt", None)),
             fmt.duration(getattr(m, "duration", None)), getattr(m, "contentRating", ""), getattr(m, "studio", ""),
             m.guid] for m in account.watchlist()]
    return columns, rows


@exporter("devices")
def devices(ctx: Context, params: dict) -> Table:
    account = ctx.account(params["uuid"])
    token = (ctx.store.account(params["uuid"]) or {}).get("authToken")
    columns = ["name", "product", "version", "platform", "platform version", "device", "model", "provides",
               "created", "last seen", "public address", "client identifier", "this workflow"]
    rows = [[d.name, d.product, d.productVersion, d.platform, d.platformVersion, d.device, d.model, d.provides,
             _date(d.createdAt), _date(d.lastSeenAt), d.publicAddress, d.clientIdentifier,
             "yes" if token and d.token == token else ""] for d in account.devices()]
    return columns, rows


@exporter("users")
def users(ctx: Context, params: dict) -> Table:
    account = ctx.account(params["uuid"])
    columns = ["name", "username", "email", "home", "restricted", "servers", "libraries"]
    rows = [[u.title, getattr(u, "username", ""), u.email, getattr(u, "home", ""), getattr(u, "restricted", ""),
             ", ".join(getattr(s, "name", "") for s in u.servers), sum(s.numLibraries or 0 for s in u.servers)]
            for u in account.users()]
    return columns, rows


# ------------------------------------------------------------------ workflow
@exporter("presets")
def presets(ctx: Context, params: dict) -> Table:
    rows = [[p.get("title"), p.get("subtitle"), p.get("arg"), p.get("id")] for p in ctx.store.presets.items]
    return ["title", "subtitle", "value", "id"], rows


def export(ctx: Context, kind: str, params: dict) -> tuple[Path, int]:
    columns, rows = EXPORTERS[kind](ctx, params)
    name = kind
    mid = params.get("mid")
    if mid:
        saved = ctx.store.server(mid) or {}
        name = f"{saved.get('friendlyName', 'server')}-{kind}"
    return write_csv(ctx.settings.downloads_dir, name, columns, rows), len(rows)


def logs_archive(ctx: Context) -> Path:
    """Zip of the workflow logs + a small environment report, to attach to a GitHub issue."""
    folder = ctx.settings.downloads_dir
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"alfred-plex-logs-{_stamp()}.zip"
    import plexapi

    report = "\n".join([
        f"workflow: {ctx.settings.version}",
        f"python: {platform.python_version()}",
        f"plexapi: {plexapi.VERSION}",
        f"macOS: {platform.mac_ver()[0]}",
        f"servers: {len(ctx.store.servers.items)}",
        f"accounts: {len(ctx.store.accounts.items)}",
    ])
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("environment.txt", report + "\n")
        for log_file in sorted(ctx.settings.cache_dir.glob("plex.log*")):
            archive.write(log_file, log_file.name)
    return path
