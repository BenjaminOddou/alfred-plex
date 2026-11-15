"""Turn Plex library objects into Alfred items.

All titles and subtitles come from attributes already present in the search
response: no extra request per row (v2 fetched ``album().tracks()`` up to
four times for every track found).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from . import alfred, fmt, nav, posters
from .alfred import Intent, Item, Mod
from .context import Context
from .filters import to_text

# plexapi class name → (media type, icon)
CLASSES = {
    "Movie": ("movie", "movie"),
    "Show": ("show", "show"),
    "Season": ("season", "show"),
    "Episode": ("episode", "show"),
    "Artist": ("artist", "person"),
    "Album": ("album", "artist"),
    "Track": ("track", "artist"),
    "Photoalbum": ("photoalbum", "photo"),
    "Photo": ("photo", "photo"),
    "Clip": ("clip", "clip"),
    "Playlist": ("playlist", "playlist"),
    "Collection": ("collection", "collection"),
    "Role": ("actor", "person"),
    "Director": ("director", "person"),
    "Genre": ("genre", "genre"),
}
NESTED = {"artist": "album", "album": "track", "show": "season", "season": "episode"}
TAGS = {"actor", "director", "genre"}
PLAYABLE_STATE = {"movie", "show", "season", "episode", "clip"}
DOWNLOADABLE = {"movie", "episode", "clip", "track", "album", "season"}
STREAMABLE = {"movie", "episode", "clip", "album", "track"}
AUDIO = {"album", "track"}
WATCHLISTABLE = {"movie", "show"}
MOD_ICONS = {
    "nested": "folder",
    "web": "web",
    "mtv": "movie_and_tv_show_search",
    "actions": "setting",
    "download": "download",
}
PEOPLE_URL = (
    "https://app.plex.tv/desktop/#!/provider/tv.plex.provider.discover/details"
    "?key=%2Flibrary%2Fpeople%2F{key}&context=search"
)


def _names(tags: Any) -> str:
    return ", ".join(t.tag for t in tags or [] if getattr(t, "tag", None))


def title(media: Any, kind: str) -> str:
    g = lambda name: getattr(media, name, None)  # noqa: E731 - short local accessor
    if kind in {"movie", "show", "album"}:
        return f"{g('title')}{fmt.year(g('year'))}"
    if kind in {"season", "photo"}:
        return fmt.join(g("parentTitle"), g("title"))
    if kind == "episode":
        return fmt.join(g("grandparentTitle"), g("title"), g("seasonEpisode"))
    if kind == "track":
        return fmt.join(g("grandparentTitle"), g("title"))
    if kind == "collection":
        years = f" ({g('minYear')} - {g('maxYear')})" if g("minYear") else ""
        return f"{g('title')}{years}"
    if kind in {"actor", "director"}:
        return g("tag") or ""
    if kind == "genre":
        return f"{g('tag')}{fmt.year(g('librarySectionTitle'))}"
    return g("title") or ""


def details(media: Any, kind: str, date_format: str) -> str:
    g = lambda name: getattr(media, name, None)  # noqa: E731
    if kind == "movie":
        return fmt.join(fmt.duration(g("duration")), g("studio") and f"Studio: {g('studio')}",
                        _names(g("directors")) and f"Director(s): {_names(g('directors'))}")
    if kind == "show":
        return fmt.join(fmt.plural(g("childCount"), "season"), g("studio") and f"Studio: {g('studio')}")
    if kind == "season":
        return fmt.join(fmt.plural(g("leafCount"), "episode"), g("parentStudio") and f"Studio: {g('parentStudio')}")
    if kind == "episode":
        return fmt.join(fmt.duration(g("duration")), fmt.day(g("originallyAvailableAt"), date_format),
                        _names(g("directors")) and f"Director(s): {_names(g('directors'))}")
    if kind == "album":
        return fmt.join(f"Artist: {g('parentTitle')}", fmt.plural(g("leafCount"), "track"),
                        g("studio") and f"Studio: {g('studio')}")
    if kind == "track":
        return fmt.join(fmt.duration(g("duration")), f"Album: {g('parentTitle')}",
                        g("trackNumber") and f"Track {g('trackNumber')}")
    if kind == "photo":
        return str(g("year") or "")
    if kind == "clip":
        return fmt.join(g("year"), g("rating") and f"Rating: {g('rating')}/10")
    if kind == "playlist":
        return fmt.join(g("playlistType"), fmt.plural(g("leafCount"), "item"),
                        fmt.day(g("addedAt"), date_format))
    if kind == "collection":
        return fmt.plural(g("childCount"), "item")
    if kind in {"actor", "director", "genre"}:
        return f"ID: {g('id')}"
    return ""


@dataclass
class Source:
    """Where a media comes from (saved server + its account)."""

    server: dict
    plex: Any  # PlexServer

    @property
    def machine_id(self) -> str:
        return self.server["machineIdentifier"]

    @property
    def account_uuid(self) -> str:
        return self.server.get("account_uuid", "")


def _escape(text: str) -> str:
    return str(text).replace("\\", "\\\\").replace("'", "\\'")


def nested_search(ctx: Context, media: Any, kind: str) -> Intent | None:
    alias = ctx.store.alias
    if kind in NESTED:
        if kind == "season":
            adv = f"{{'season.index': {media.index}, 'show.title=': '{_escape(media.parentTitle)}'}}"
        elif kind == "album":
            adv = f"{{'album.title=': '{_escape(media.title)}', 'artist.title=': '{_escape(media.parentTitle)}'}}"
        else:
            adv = f"{{'{kind}.title=': '{_escape(media.title)}'}}"
        return alfred.search(to_text(alias, [("libtype", NESTED[kind]), ("advancedFilters", adv)]))
    if kind in {"actor", "director"}:
        return alfred.search(to_text(alias, [(kind, media.id)]))
    if kind == "collection":
        return alfred.search(to_text(alias, [("collection", media.index)]))
    if kind == "genre":
        from plexapi.utils import reverseSearchType

        libtype = reverseSearchType(media.librarySectionType)
        return alfred.search(to_text(alias, [("libtype", libtype), ("genre", media.id)]))
    return None


def web_url(media: Any, kind: str) -> str | None:
    if kind in {"genre", "photo"}:
        return None
    if kind in {"actor", "director"}:
        return PEOPLE_URL.format(key=quote(str(media.tagKey), safe="")) if getattr(media, "tagKey", None) else None
    return media.getWebURL()


def tmdb_id(media: Any) -> str | None:
    for guid in getattr(media, "guids", None) or []:
        if str(guid.id).startswith("tmdb://"):
            return guid.id.split("://", 1)[1]
    return None


def stream_intent(ctx: Context, src: Source, media: Any, kind: str) -> Intent:
    if kind not in AUDIO and len(getattr(media, "media", None) or []) > 1:
        return alfred.search(nav=nav.join("search", "streams", src.machine_id, media.ratingKey))
    return alfred.run("stream", mid=src.machine_id, key=media.key, type=kind, media=0, part=0)


def watchlist_intent(ctx: Context, uuid: str, guid: str, label: str, kind: str,
                     on_list: bool, then: Intent) -> tuple[Intent, str, str]:
    action = "remove" if on_list else "add"
    subtitle = f"Press ⏎ to {action} the {kind} {'from' if on_list else 'to'} your watchlist"
    intent = alfred.run("watchlist", then=then, uuid=uuid, guid=guid, title=label, add=not on_list)
    return intent, subtitle, "delete" if on_list else "add"


def page_intent(src: Source, media: Any) -> Intent:
    """Media actions page (played, rating, files, playlists, download...)."""
    return alfred.browse(nav.join("media", src.machine_id, media.ratingKey))


def played_intent(src: Source, media: Any, label: str, then: Intent) -> tuple[Intent, str, str]:
    played = bool(getattr(media, "isPlayed", False))
    intent = alfred.run("media.played", then=then, mid=src.machine_id, key=media.ratingKey, title=label,
                        played=not played)
    return intent, f"Press ⏎ to mark as {'unplayed' if played else 'played'}", "ok" if not played else "return"


MORE_PREFIX = "alfred-plex:"


def more_marker(path: str) -> str:
    """Raw form of a → target (still accepted by ``main.py more``)."""
    return f"{MORE_PREFIX}{path}"


def prefetch_posters(ctx: Context, found: list[tuple[Source, Any]]) -> None:
    """Download the posters of a list when the "List with posters" view is chosen (in parallel)."""
    if not ctx.settings.list_posters:
        return
    by_source: dict[str, tuple[Source, list[Any]]] = {}
    for src, media in found:
        kind = CLASSES.get(type(media).__name__, (None, None))[0]
        if kind and kind not in TAGS:
            by_source.setdefault(src.machine_id, (src, []))[1].append(media)
    from .plex import parallel

    parallel(lambda job: posters.server_posters(ctx.settings, job[0].plex, job[1]), list(by_source.values()))


def attach(item: Item, key: str, intent: Intent | None, subtitle: str, icon_name: str) -> None:
    """Bind an action to ⏎ (``key == "arg"``) or to a modifier key."""
    if not key or intent is None:
        return
    if key == "arg":
        item.intent = intent
    else:
        item.mods[key] = Mod(subtitle, intent, alfred.icon(icon_name))


def to_item(ctx: Context, src: Source, media: Any, watchlist: set[str], here: Intent) -> Item | None:
    """Alfred row for a library media. ``here`` is the page shown again after a command."""
    kind, image = CLASSES.get(type(media).__name__, (None, None))
    if kind is None:
        return None
    keys = ctx.settings.shortcuts
    label = title(media, kind)
    subtitle = fmt.join(src.server.get("friendlyName"), kind, details(media, kind, ctx.settings.date_format))
    guid = getattr(media, "guid", None)
    on_list = kind in WATCHLISTABLE and guid in watchlist
    item = Item(
        label,
        subtitle,
        icon=alfred.icon(f"{image}_bookmarked" if on_list else image),
        key=f"{label}\0{subtitle}",
        text=label,
    )
    thumb = getattr(media, "thumb", None)
    if thumb and kind not in TAGS:
        item.quicklook = src.plex.url(thumb, includeToken=True)
        if ctx.settings.list_posters:  # "List with posters" view: prefetched by prefetch_posters()
            poster = posters.cached(ctx.settings, src.machine_id, thumb)
            if poster:
                item.icon = str(poster)
    if kind not in TAGS:
        item.action = f"{label} · {src.server.get('friendlyName') or 'Plex'}"
        item.arrow = nav.join("more", src.machine_id, media.ratingKey)
        attach(item, keys.actions, page_intent(src, media),
               "Press ⏎ to see all the actions on this media", MOD_ICONS["actions"])
        if getattr(media, "isPlayed", None) is not None and kind in PLAYABLE_STATE:
            attach(item, keys.played, *played_intent(src, media, label, here))
            if media.isPlayed:
                item.subtitle = f"✓ {item.subtitle}"
        if kind in DOWNLOADABLE:
            attach(item, keys.download, alfred.run("media.download", mid=src.machine_id, key=media.ratingKey,
                                                   title=label),
                   "Press ⏎ to download the file(s) to your downloads folder", MOD_ICONS["download"])

    attach(item, keys.nested_search, nested_search(ctx, media, kind),
           "Press ⏎ to trigger a nested search", MOD_ICONS["nested"])
    url = web_url(media, kind)
    attach(item, keys.web, alfred.open_url(url) if url else None,
           "Press ⏎ to open the media in plex web", MOD_ICONS["web"])
    player = ctx.settings.media_player
    if kind in STREAMABLE and not (kind in AUDIO and player == "infuse"):
        attach(item, keys.stream, stream_intent(ctx, src, media, kind),
               f"Press ⏎ to play the media with {player.upper()}", player)
    if kind in WATCHLISTABLE and guid:
        tmdb = tmdb_id(media)
        prefix = "m" if kind == "movie" else "t"
        mtv = alfred.mtv(f"{prefix}:{tmdb}") if tmdb else alfred.run(
            "mtv", uuid=src.account_uuid, type=kind, key=guid.rsplit("/", 1)[-1])
        attach(item, keys.mtv, mtv,
               "Press ⏎ to get media infos using Movie and TV Show Search workflow", MOD_ICONS["mtv"])
        if guid.startswith("plex://"):
            intent, sub, icon_name = watchlist_intent(ctx, src.account_uuid, guid, label, kind, on_list, here)
            attach(item, keys.watchlist, intent, sub, icon_name)
    if item.intent is None and kind not in TAGS:
        # ⏎ is free for this media: open its actions page, so every row does something
        item.intent = page_intent(src, media)
    return item
