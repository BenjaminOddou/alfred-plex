"""Media actions page: everything you can do with one media, in one place.

Opened with ⏎ on a movie / episode / track (or the "Media actions" shortcut)
from Plex Search, recently added, continue watching...
"""

from __future__ import annotations

import os
from typing import Any

from .. import alfred, fmt, nav
from .. import details as sheets
from ..alfred import Intent, Item, Mod
from ..context import Context
from ..media import (
    AUDIO,
    CLASSES,
    DOWNLOADABLE,
    NESTED,
    PLAYABLE_STATE,
    STREAMABLE,
    WATCHLISTABLE,
    Source,
    details,
    nested_search,
    stream_intent,
    title,
    tmdb_id,
    watchlist_intent,
    web_url,
)
from . import page

VIDEO_KINDS = {"movie", "show", "season", "episode", "clip"}


def _load(ctx: Context, mid: str, key: str) -> tuple[Source, Any, str]:
    plex = ctx.server(mid)
    media = plex.fetchItem(int(key))
    kind = CLASSES.get(type(media).__name__, (media.type, media.type))[0]
    return Source(ctx.store.server(mid) or {}, plex), media, kind


def _here(ctx: Context, mid: str, key: str, *sub: str) -> Intent:
    return alfred.browse(nav.join("media", mid, key, *sub))


def resolution(value: object) -> str | None:
    """``1080`` → ``1080p``, ``4k`` stays ``4k``."""
    if not value:
        return None
    return f"{value}p" if str(value).isdigit() else str(value)


def _files(ctx: Context, src: Source, media: Any, label: str) -> list[Item]:
    items = []
    for version in getattr(media, "media", None) or []:
        for part in version.parts:
            path = part.file or ""
            name = os.path.basename(path) or f"Part {part.id}"
            link = src.plex.url(part.key, includeToken=True)
            local = bool(path) and os.path.exists(path)
            intent = alfred.reveal(path) if local else alfred.run("clipboard", text=path, label="File path")
            items.append(Item(
                f"📄 {name}",
                fmt.join(fmt.size(part.size), part.container, resolution(version.videoResolution),
                         version.videoCodec, version.audioCodec, version.bitrate and f"{version.bitrate} kbps",
                         "⏎ show in Finder" if local else "⏎ copy path"),
                intent=intent,
                icon=alfred.icon("document"),
                text=path,
                mods={"cmd": Mod("Press ⏎ to copy the direct stream link",
                                 alfred.run("clipboard", text=link, label="Stream link"), alfred.icon("web"))},
            ))
    return items


def _info(ctx: Context, media: Any) -> Item:
    g = lambda name: getattr(media, name, None)  # noqa: E731
    genres = ", ".join(t.tag for t in g("genres") or [])
    ratings = fmt.join(g("audienceRating") and f"Audience {g('audienceRating')}/10",
                       g("rating") and f"Critics {g('rating')}/10",
                       g("userRating") and f"You {g('userRating')}/10")
    text = fmt.join(
        g("addedAt") and f"Added {fmt.day(g('addedAt'), ctx.settings.date_format)}",
        g("lastViewedAt") and f"Last viewed {fmt.ago(g('lastViewedAt'))}",
        f"Played {fmt.plural(g('viewCount'), 'time')}" if g("viewCount") is not None else None,
        g("contentRating"), genres, ratings,
    )
    summary = g("summary") or ""
    return Item("ℹ️ Infos", text or "No extra information", icon=alfred.icon("info"),
                text=f"{text}\n\n{summary}".strip())


@page("media/<mid>/<key>")
def media_page(ctx: Context, mid: str, key: str) -> list[Item]:
    src, media, kind = _load(ctx, mid, key)
    here = _here(ctx, mid, key)
    origin = alfred.pop(ctx.history)  # where the user came from (shown again after a deletion)
    label = title(media, kind)
    header = Item(label, fmt.join(src.server.get("friendlyName"), kind, details(media, kind, ctx.settings.date_format)),
                  icon=alfred.icon(CLASSES.get(type(media).__name__, (kind, "movie"))[1]), text=label)
    if getattr(media, "thumb", None):
        header.quicklook = src.plex.url(media.thumb, includeToken=True)
    items = [header]
    player = ctx.settings.media_player

    if kind in STREAMABLE and not (kind in AUDIO and player == "infuse"):
        items.append(Item(f"▶️ Play with {player.upper()}", "Stream the media on this Mac",
                          intent=stream_intent(ctx, src, media, kind), icon=alfred.icon(player)))
    # Written now, so the Text View opens on top of this page: Esc comes back here.
    try:
        sheet = alfred.details(str(sheets.prepare(ctx, src.plex, media, mid)))
    except Exception:  # noqa: BLE001 - the sheet is a bonus, keep the page usable
        sheet = alfred.run("media.details", mid=mid, key=key)
    items.append(Item("📖 Full details", "Poster, summary, cast, crew, ratings, files and streams ǀ ⎋ to come back",
                      intent=sheet, icon=alfred.icon("info")))
    if kind in {"show", "season", "artist", "album", "collection", "playlist"}:
        items.append(Item("🖼️ Show its content as posters", "Seasons, episodes, albums, tracks or items",
                          intent=alfred.grid(nav.join("grid", "children", mid, key)),
                          icon=alfred.icon("photo")))
    nested = nested_search(ctx, media, kind) if kind in NESTED else None
    if nested:
        items.append(Item(f"📂 Browse the {NESTED[kind]}s", "Nested search on this media",
                          intent=nested, icon=alfred.icon("folder")))
    if kind in {"episode", "track", "season", "album"}:
        for prefix in ("grandparent", "parent"):
            parent_key = getattr(media, f"{prefix}RatingKey", None)
            if parent_key:
                name = getattr(media, f"{prefix}Title", None) or prefix
                items.append(Item(f"⬆️ Go to {name}", "Open its actions page",
                                  intent=alfred.browse(nav.join("media", mid, parent_key)),
                                  icon=alfred.icon("return")))
    url = web_url(media, kind)
    if url:
        items.append(Item("🌐 Open in Plex Web", url, intent=alfred.open_url(url), icon=alfred.icon("web")))
    if kind in PLAYABLE_STATE:
        played = bool(getattr(media, "isPlayed", False))
        items.append(Item(
            "⭕ Mark as unplayed" if played else "✅ Mark as played",
            "Currently played" if played else "Currently not played",
            intent=alfred.run("media.played", then=here, mid=mid, key=key, title=label, played=not played),
            icon=alfred.icon("return" if played else "ok"),
        ))
    if kind not in {"playlist", "collection"}:
        rating = getattr(media, "userRating", None)
        items.append(Item(
            "⭐ Rate", f"Your rating: {rating}/10" if rating else "Not rated yet",
            intent=alfred.ask(f"Rate {label}", "A number from 0 to 10 (decimals allowed), empty to clear",
                              "media.rate", then=here, mid=mid, key=key, title=label),
            icon=alfred.icon("statistics"),
        ))
    guid = getattr(media, "guid", "") or ""
    uuid = src.account_uuid
    if kind in WATCHLISTABLE and guid.startswith("plex://") and uuid:
        on_list = guid in ctx.watchlist(uuid)
        intent, _, icon_name = watchlist_intent(ctx, uuid, guid, label, kind, on_list, here)
        items.append(Item("🔖 Remove from watchlist" if on_list else "🔖 Add to watchlist",
                          "Your plex watchlist", intent=intent, icon=alfred.icon(icon_name)))
        tmdb = tmdb_id(media)
        if tmdb:
            items.append(Item("🎬 Movie and TV Show Search", "Infos, cast, trailers...",
                              intent=alfred.mtv(f"{'m' if kind == 'movie' else 't'}:{tmdb}"),
                              icon=alfred.icon("movie_and_tv_show_search")))
    if kind not in {"playlist", "collection", "photoalbum", "photo"}:
        items.append(Item("➕ Add to a playlist", "Choose or create a playlist",
                          intent=alfred.browse(nav.join("media", mid, key, "playlists")),
                          icon=alfred.icon("playlist")))
    if kind not in {"playlist", "collection", "episode", "track", "season"}:
        items.append(Item("🗂️ Collections", "Add to or remove from a collection",
                          intent=alfred.browse(nav.join("media", mid, key, "collections")),
                          icon=alfred.icon("collection")))
    items += _files(ctx, src, media, label)
    if kind in DOWNLOADABLE:
        items.append(Item("⬇️ Download", f"Save the file(s) in {ctx.settings.downloads_dir}",
                          intent=alfred.run("media.download", mid=mid, key=key, title=label),
                          icon=alfred.icon("download")))
    items += [
        Item("🔄 Refresh metadata", "Download fresh infos and artwork from the internet",
             intent=alfred.run("media.refresh", then=here, mid=mid, key=key, title=label), icon=alfred.icon("refresh")),
        Item("🔍 Analyze", "Analyze the media file(s) (codecs, loudness...)",
             intent=alfred.run("media.analyze", then=here, mid=mid, key=key, title=label), icon=alfred.icon("scan")),
        _info(ctx, media),
        Item("🗑️ Delete from the server", "Deletes the file(s)! Needs 'Allow media deletion' in the server settings",
             intent=alfred.confirm(f"Delete {label}?", "The file(s) will be deleted from the server disk",
                                   alfred.run("media.delete", then=origin or alfred.search(),
                                              mid=mid, key=key, title=label)),
             icon=alfred.icon("delete")),
    ]
    return items


@page("media/<mid>/<key>/playlists")
def playlists(ctx: Context, mid: str, key: str) -> list[Item]:
    src, media, kind = _load(ctx, mid, key)
    label = title(media, kind)
    wanted = "video" if kind in VIDEO_KINDS else "audio" if kind in AUDIO | {"artist"} else "photo"
    back = alfred.pop(ctx.history) or alfred.browse(nav.join("media", mid, key))
    items = [Item("➕ New playlist", f"Create a {wanted} playlist with {label}",
                  intent=alfred.ask("Playlist name", f"New playlist with {label}", "media.playlist_new",
                                    then=back, mid=mid, key=key, title=label),
                  icon=alfred.icon("add"))]
    for playlist in src.plex.playlists(playlistType=wanted):
        if getattr(playlist, "smart", False):
            continue
        items.append(Item(playlist.title, fmt.join(fmt.plural(playlist.leafCount, "item"), "⏎ add the media"),
                          intent=alfred.run("media.playlist", then=back, mid=mid, key=key, title=label,
                                            playlist=playlist.ratingKey, name=playlist.title),
                          icon=alfred.icon("playlist")))
    return items


@page("media/<mid>/<key>/collections")
def collections(ctx: Context, mid: str, key: str) -> list[Item]:
    src, media, kind = _load(ctx, mid, key)
    label = title(media, kind)
    current = {t.tag for t in getattr(media, "collections", None) or []}
    here = _here(ctx, mid, key, "collections")
    items = [Item("➕ New collection", f"Create a collection with {label}",
                  intent=alfred.ask("Collection name", f"New collection with {label}", "media.collection",
                                    then=here, mid=mid, key=key, title=label, add=True),
                  icon=alfred.icon("add"))]
    section = src.plex.library.sectionByID(media.librarySectionID)
    names = sorted({c.title for c in section.collections()} | current)
    for name in names:
        member = name in current
        items.append(Item(
            f"{'✓ ' if member else ''}{name}",
            "⏎ remove the media from this collection" if member else "⏎ add the media to this collection",
            intent=alfred.run("media.collection", then=here, mid=mid, key=key, title=label, name=name, add=not member),
            icon=alfred.icon("collection"),
        ))
    return items
