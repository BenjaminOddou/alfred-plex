"""Media commands: watchlist, local streaming, Movie and TV Show Search."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace
from urllib.parse import quote

from .. import alfred, plex
from ..alfred import Intent
from ..context import Context
from ..system import failure, log, success, warning, which
from . import command, then

VLC_ARGS = ["-I", "macosx", "--no-xlib", "--no-video-title-show", "--video-on-top"]
# Process names killed before a new stream so that a single player instance is kept.
PLAYER_PROCESSES = {"vlc": "VLC", "iina": "IINA"}


@command("watchlist")
def watchlist(ctx: Context, text: str) -> Intent | None:
    """Add / remove with the official plexapi watchlist API (it validates the state first)."""
    from plexapi.exceptions import BadRequest

    data = ctx.payload
    uuid, add = data["uuid"], bool(data.get("add"))
    account = ctx.account(uuid)
    # addToWatchlist only needs .guid and .title: no need to fetch the full metadata.
    item = SimpleNamespace(guid=data["guid"], title=data.get("title", ""))
    try:
        (account.addToWatchlist if add else account.removeFromWatchlist)(item)
    except BadRequest as error:  # already in the wanted state: just resync the cache
        log.info("Watchlist already up to date: %s", error)
    plex.update_watchlist_cache(ctx.settings, uuid, data["guid"], add)
    verb = "added to" if add else "removed from"
    success(ctx.settings, f"{data.get('title', 'Media')} was {verb} the watchlist of {account.friendlyName}")
    return then(ctx)


def build_player_command(player: str, binary: str, urls: list[str], titles: list[str], audio: bool) -> list[str]:
    if player == "infuse":
        return ["open", f"infuse://x-callback-url/play?url={quote(urls[0], safe='')}"]
    if player == "vlc":
        args = [binary, *VLC_ARGS]
        option = "--meta-title" if audio else "--input-title-format"
        for url, title in zip(urls, titles, strict=True):
            args += [option, title, url]
        return args
    args = [binary] + (["--music-mode"] if audio else [])
    for url, title in zip(urls, titles, strict=True):
        args += [url, f"--mpv-force-media-title={title}", "--no-stdin"]
    return args


def stream_targets(server, media, kind: str, media_index: int, part_index: int) -> tuple[list[str], list[str]]:
    if kind == "album":
        tracks = media.tracks()
        urls = [server.url(t.media[0].parts[0].key, includeToken=True) for t in tracks]
        titles = [f"{media.parentTitle} ǀ {media.title} ǀ {t.title} {t.trackNumber} / {len(tracks)}" for t in tracks]
        return urls, titles
    part = media.media[media_index].parts[part_index]
    if kind == "episode":
        title = f"{media.grandparentTitle} ǀ {media.title} ǀ {media.seasonEpisode}"
    elif kind == "track":
        title = f"{media.grandparentTitle} ǀ {media.parentTitle} ǀ {media.title}"
    elif kind == "movie":
        title = f"{media.title} ({media.year})"
    else:
        title = media.title
    return [server.url(part.key, includeToken=True)], [title]


@command("stream")
def stream(ctx: Context, text: str) -> None:
    player = ctx.settings.media_player
    binary = "open" if player == "infuse" else which(player)
    if not binary:
        warning(ctx.settings, f"Can't find the {player} command line tool, see the README to install it")
        return
    data = ctx.payload
    server = ctx.server(data["mid"])
    media = server.fetchItem(data["key"])
    kind = data.get("type", media.type)
    urls, titles = stream_targets(server, media, kind, int(data.get("media", 0)), int(data.get("part", 0)))
    if player in PLAYER_PROCESSES:
        subprocess.run(["pkill", "-x", PLAYER_PROCESSES[player]], check=False)
    command_line = build_player_command(player, binary, urls, titles, kind in {"album", "track"})
    token = getattr(server, "_token", None)
    shown = " ".join(command_line)
    log.debug("Starting stream: %s", shown.replace(token, "***") if token else shown)
    subprocess.Popen(command_line, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


@command("mtv")
def movie_tv_search(ctx: Context, text: str) -> Intent | None:
    """Find the TMDB id, then call the Movie and TV Show Search workflow."""
    data = ctx.payload
    try:
        guids = plex.online_guids(ctx.account(data["uuid"]), data["key"])
    except Exception as error:  # noqa: BLE001
        failure(ctx.settings, "Can't get the media infos from plex", error)
        return alfred.done()
    tmdb = next((g.split("://", 1)[1] for g in guids if g.startswith("tmdb://")), None)
    if not tmdb:
        warning(ctx.settings, "No TMDB id found for this media")
        return alfred.done()
    return alfred.mtv(f"{'m' if data.get('type') == 'movie' else 't'}:{tmdb}")


# ------------------------------------------------------------- media actions
def _media(ctx: Context):
    server = ctx.server(ctx.payload["mid"])
    return server, server.fetchItem(int(ctx.payload["key"]))


def parse_rating(text: str) -> float | None:
    """``"8"`` → 8.0, ``""`` → None (clear). Raises ValueError outside 0-10."""
    text = text.strip().replace(",", ".")
    if not text or text.lower() in {"clear", "none", "0"}:
        return None
    value = float(text)
    if not 0 <= value <= 10:
        raise ValueError("a rating goes from 0 to 10")
    return value


@command("media.played")
def played(ctx: Context, text: str) -> None:
    _, media = _media(ctx)
    title = ctx.payload.get("title", media.title)
    if ctx.payload.get("played", True):
        media.markPlayed()
        success(ctx.settings, f"{title} is marked as played")
    else:
        media.markUnplayed()
        success(ctx.settings, f"{title} is marked as unplayed")


@command("media.rate")
def rate(ctx: Context, text: str) -> None:
    try:
        rating = parse_rating(text)
    except ValueError as error:
        warning(ctx.settings, f"Invalid rating: {error}")
        return
    _, media = _media(ctx)
    media.rate(rating)
    title = ctx.payload.get("title", media.title)
    success(ctx.settings, f"{title} rated {rating}/10" if rating is not None else f"Rating of {title} cleared")


@command("media.refresh")
def refresh_media(ctx: Context, text: str) -> None:
    _, media = _media(ctx)
    media.refresh()
    success(ctx.settings, f"Metadata refresh started for {ctx.payload.get('title', media.title)}")


@command("media.analyze")
def analyze(ctx: Context, text: str) -> None:
    _, media = _media(ctx)
    media.analyze()
    success(ctx.settings, f"Analysis started for {ctx.payload.get('title', media.title)}")


@command("media.delete")
def delete(ctx: Context, text: str) -> None:
    from plexapi.exceptions import BadRequest, Unauthorized

    _, media = _media(ctx)
    title = ctx.payload.get("title", media.title)
    try:
        media.delete()
    except (BadRequest, Unauthorized) as error:
        failure(ctx.settings, "Deletion refused: enable 'Allow media deletion' in the server settings", error)
        return
    success(ctx.settings, f"{title} is deleted from the server")


@command("media.download")
def download(ctx: Context, text: str) -> Intent | None:
    _, media = _media(ctx)
    title = ctx.payload.get("title", media.title)
    folder = ctx.settings.downloads_dir
    folder.mkdir(parents=True, exist_ok=True)
    from ..system import notify

    notify(ctx.settings, "⏳ Please wait!", f"Downloading {title}...")
    files = media.download(savepath=str(folder), keep_original_name=True)
    files = files if isinstance(files, list) else [files]
    success(ctx.settings, f"{title} downloaded ({len(files)} file(s)) in {folder}")
    return alfred.reveal(str(files[0])) if files else None


@command("media.playlist")
def add_to_playlist(ctx: Context, text: str) -> None:
    server, media = _media(ctx)
    playlist = server.fetchItem(f"/playlists/{ctx.payload['playlist']}")
    playlist.addItems([media])
    success(ctx.settings, f"{ctx.payload.get('title', media.title)} added to the playlist {playlist.title}")


@command("media.playlist_new")
def new_playlist(ctx: Context, text: str) -> None:
    name = text.strip()
    if not name:
        warning(ctx.settings, "A playlist needs a name")
        return
    server, media = _media(ctx)
    server.createPlaylist(name, items=[media])
    success(ctx.settings, f"Playlist {name} created with {ctx.payload.get('title', media.title)}")


@command("media.collection")
def collection(ctx: Context, text: str) -> None:
    name = (ctx.payload.get("name") or text).strip()
    if not name:
        warning(ctx.settings, "A collection needs a name")
        return
    _, media = _media(ctx)
    title = ctx.payload.get("title", media.title)
    if ctx.payload.get("add", True):
        media.addCollection(name)
        success(ctx.settings, f"{title} added to the collection {name}")
    else:
        media.removeCollection(name)
        success(ctx.settings, f"{title} removed from the collection {name}")


@command("clipboard")
def clipboard(ctx: Context, text: str) -> None:
    value = ctx.payload.get("text", "")
    subprocess.run(["pbcopy"], input=value.encode(), check=False)
    success(ctx.settings, f"{ctx.payload.get('label', 'Text')} copied to the clipboard")


@command("media.details")
def media_details(ctx: Context, text: str) -> Intent:
    """Write the Markdown sheet of a media, then show it in the Text View."""
    from .. import details

    server, media = _media(ctx)
    return alfred.details(str(details.prepare(ctx, server, media, ctx.payload["mid"])))
