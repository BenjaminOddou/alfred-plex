"""Poster images for Alfred's Grid View (and list icons when already cached).

Posters are resized by the Plex server (``transcodeImage``) and kept in the
cache folder: the file name contains a hash of the thumb key, which changes
when the artwork changes, so a poster is downloaded once.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from .plex import parallel
from .settings import Settings

log = logging.getLogger("alfred_plex")

WIDTH, HEIGHT = 300, 450  # 2:3 posters, sharp enough for 3 to 8 columns
MAX_FILES = 3000


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


def _download(session: Any, url: str, target: Path, timeout: int = 10) -> Path:
    response = session.get(url, timeout=timeout)
    if getattr(response, "status_code", 200) >= 400:
        raise OSError(f"HTTP {response.status_code}")
    tmp = target.with_suffix(".part")
    tmp.write_bytes(response.content)
    tmp.replace(target)
    return target


def server_posters(settings: Settings, plex: Any, medias: list[Any]) -> dict[str, Path]:
    """{ratingKey: poster path} for library medias, downloading the missing ones in parallel."""
    source = plex.machineIdentifier
    wanted, result = [], {}
    for media in medias:
        thumb = getattr(media, "thumb", None) or getattr(media, "parentThumb", None)
        if not thumb:
            continue
        path = path_for(settings, source, thumb)
        if path.exists():
            result[str(media.ratingKey)] = path
        else:
            wanted.append((str(media.ratingKey), thumb, path))

    def fetch(job):
        key, thumb, path = job
        url = plex.transcodeImage(thumb, HEIGHT, WIDTH, minSize=True, upscale=True)
        return key, _download(plex._session, url, path)

    for item in parallel(fetch, wanted, workers=8):
        if not isinstance(item, Exception):
            result[item[0]] = item[1]
    if wanted:
        prune(settings)
    return result


def url_posters(settings: Settings, session: Any, urls: dict[str, str]) -> dict[str, Path]:
    """{key: poster path} for absolute image URLs (Discover / watchlist)."""
    result, wanted = {}, []
    for key, url in urls.items():
        if not url:
            continue
        path = path_for(settings, "url", url)
        if path.exists():
            result[key] = path
        else:
            wanted.append((key, url, path))
    for item in parallel(lambda job: (job[0], _download(session, job[1], job[2])), wanted, workers=8):
        if not isinstance(item, Exception):
            result[item[0]] = item[1]
    return result


def prune(settings: Settings, keep: int = MAX_FILES) -> None:
    files = sorted(folder(settings).glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[keep:]:
        old.unlink(missing_ok=True)
