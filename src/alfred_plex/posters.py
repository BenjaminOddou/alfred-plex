"""Poster images for the Grid View, list icons and the details pages.

Posters live in Alfred's workflow cache folder (``alfred_workflow_cache``),
in ``posters/``. Plex servers resize them (``transcodeImage``), Discover
images go through the Plex image resizer. The file name is a hash of the
thumb key, which changes when the artwork changes, so a poster is downloaded
once.

``posters/index.json`` remembers what each file is (title, type, server), so
the cache can be listed in Plex Help and purged in one go or one poster at
a time.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .plex import parallel
from .settings import Settings

log = logging.getLogger("alfred_plex")

WIDTH, HEIGHT = 300, 450  # 2:3 posters, sharp enough for 3 to 8 columns
MAX_FILES = 3000
INDEX = "index.json"
_INDEX_LOCK = threading.Lock()  # posters of several servers are downloaded in parallel
# Plex image resizer for absolute URLs (Discover, watchlist): small files instead of TMDB originals.
RESIZER = "https://images.plex.tv/photo?height={h}&width={w}&minSize=1&upscale=1&url={url}"
DISCOVER_IMAGES = "https://metadata-static.plex.tv"


def folder(settings: Settings) -> Path:
    path = settings.cache_dir / "posters"
    path.mkdir(parents=True, exist_ok=True)
    return path


def path_for(settings: Settings, source: str, thumb: str) -> Path:
    digest = hashlib.sha1(f"{source}|{thumb}".encode()).hexdigest()[:20]
    return folder(settings) / f"{digest}.jpg"


def cached(settings: Settings, source: str, thumb: str | None) -> Path | None:
    """Poster file if it was already downloaded (no network)."""
    if not thumb:
        return None
    path = path_for(settings, source, thumb)
    return path if path.exists() else None


def absolute(url: str | None) -> str:
    """Discover sometimes answers ``/library/...`` image paths: make them absolute."""
    url = str(url or "")
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("/"):
        return f"{DISCOVER_IMAGES}{url}"
    return url if url.startswith("http") else ""


# ------------------------------------------------------------------- index
def _index_path(settings: Settings) -> Path:
    return folder(settings) / INDEX


def read_index(settings: Settings) -> dict[str, dict]:
    try:
        data = json.loads(_index_path(settings).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_index(settings: Settings, data: dict[str, dict]) -> None:
    path = _index_path(settings)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def remember(settings: Settings, entries: dict[str, dict]) -> None:
    """Add ``{file name: {title, kind, source}}`` to the index."""
    if not entries:
        return
    now = int(time.time())
    with _INDEX_LOCK:
        data = read_index(settings)
        for name, meta in entries.items():
            data[name] = {**{k: v for k, v in meta.items() if v}, "at": now}
        try:
            _write_index(settings, data)
        except OSError as error:  # the index is a nice-to-have
            log.debug("Poster index not written: %s", error)


def entries(settings: Settings) -> list[tuple[Path, dict]]:
    """Cached posters, most recent first, with what they show (when known)."""
    index = read_index(settings)
    files = [p for p in folder(settings).glob("*.jpg") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [(path, index.get(path.name, {})) for path in files]


def usage(settings: Settings) -> tuple[int, int]:
    """(number of posters, total size in bytes)."""
    files = [p for p in folder(settings).glob("*.jpg") if p.is_file()]
    return len(files), sum(p.stat().st_size for p in files)


def remove(settings: Settings, name: str) -> bool:
    """Delete one poster (it comes back the next time it is shown)."""
    path = folder(settings) / Path(name).name  # never leave the posters folder
    if path.suffix != ".jpg" or not path.exists():
        return False
    path.unlink(missing_ok=True)
    with _INDEX_LOCK:
        data = read_index(settings)
        if data.pop(path.name, None) is not None:
            _write_index(settings, data)
    return True


def purge(settings: Settings) -> tuple[int, int]:
    """Delete every poster: (files removed, bytes freed)."""
    count, size = usage(settings)
    for path in folder(settings).glob("*"):
        if path.is_file():
            path.unlink(missing_ok=True)
    return count, size


# --------------------------------------------------------------- downloads
def _download(session: Any, url: str, target: Path, timeout: int = 10) -> Path:
    response = session.get(url, timeout=timeout)
    if getattr(response, "status_code", 200) >= 400:
        raise OSError(f"HTTP {response.status_code}")
    content = response.content
    if not content:
        raise OSError("empty image")
    tmp = target.with_suffix(".part")
    tmp.write_bytes(content)
    tmp.replace(target)
    return target


def _thumb(media: Any) -> str | None:
    return getattr(media, "thumb", None) or getattr(media, "parentThumb", None) \
        or getattr(media, "grandparentThumb", None)


def server_poster(settings: Settings, plex: Any, media: Any) -> Path | None:
    """Poster of one library media, from the cache only (no network)."""
    return cached(settings, plex.machineIdentifier, _thumb(media))


def server_posters(settings: Settings, plex: Any, medias: list[Any]) -> dict[str, Path]:
    """{ratingKey: poster path} for library medias, downloading the missing ones in parallel."""
    source = plex.machineIdentifier
    wanted, result = [], {}
    for media in medias:
        thumb = _thumb(media)
        if not thumb or getattr(media, "ratingKey", None) is None:
            continue
        path = path_for(settings, source, thumb)
        if path.exists():
            result[str(media.ratingKey)] = path
        else:
            wanted.append((media, thumb, path))

    def fetch(job):
        media, thumb, path = job
        url = plex.transcodeImage(thumb, HEIGHT, WIDTH, minSize=True, upscale=True)
        return media, _download(plex._session, url, path)

    found = {}
    for item in parallel(fetch, wanted, workers=8):
        if isinstance(item, Exception):
            continue
        media, path = item
        result[str(media.ratingKey)] = path
        found[path.name] = {"title": _label(media), "kind": getattr(media, "type", ""),
                            "source": getattr(plex, "friendlyName", "")}
    if found:
        remember(settings, found)
        prune(settings)
    return result


def _label(media: Any) -> str:
    title = getattr(media, "title", "") or ""
    parent = getattr(media, "grandparentTitle", None) or getattr(media, "parentTitle", None)
    kind = getattr(media, "type", "")
    if kind in {"episode", "season", "track", "album"} and parent:
        return f"{parent} ǀ {title}"
    year = getattr(media, "year", None)
    return f"{title} ({year})" if year and kind in {"movie", "show"} else title


def url_posters(settings: Settings, session: Any, urls: dict[str, str],
                labels: dict[str, dict] | None = None, resize: bool = True,
                source: str = "Plex Discover") -> dict[str, Path]:
    """{key: poster path} for absolute image URLs (Discover / watchlist / user avatars).

    ``labels`` ({key: {title, kind}}) feeds the cache index.
    """
    result, wanted = {}, []
    for key, url in urls.items():
        url = absolute(url)
        if not url:
            continue
        path = path_for(settings, "url", url)
        if path.exists():
            result[key] = path
        else:
            wanted.append((key, url, path))

    def fetch(job):
        key, url, path = job
        if not resize:
            return key, _download(session, url, path)
        try:  # resized by Plex: a few KB instead of the original artwork
            return key, _download(session, RESIZER.format(h=HEIGHT, w=WIDTH, url=quote(url, safe="")), path)
        except Exception:  # noqa: BLE001 - fall back on the original image
            return key, _download(session, url, path)

    found = {}
    for item in parallel(fetch, wanted, workers=8):
        if isinstance(item, Exception):
            continue
        key, path = item
        result[key] = path
        found[path.name] = {**(labels or {}).get(key, {}), "source": source}
    if found:
        remember(settings, found)
        prune(settings)
    return result


# ----------------------------------------------------------------- avatars
def web_session() -> Any:
    """Plain HTTP session: plex.tv avatars are public images."""
    import requests

    return requests.Session()


def avatars(settings: Settings, session: Any, users: dict[str, tuple[str, str | None]]) -> dict[str, Path]:
    """{key: avatar path} for ``{key: (name, avatar url)}``: plex.tv user pictures, kept with the posters."""
    urls = {key: url for key, (_, url) in users.items() if url}
    labels = {key: {"title": name, "kind": "user"} for key, (name, _) in users.items()}
    return url_posters(settings, session, urls, labels, resize=False, source="Plex users")


def prune(settings: Settings, keep: int = MAX_FILES) -> None:
    files = sorted(folder(settings).glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[keep:]:
        old.unlink(missing_ok=True)
