"""More details page: from the media actions page, or → on a media row (``➡️ Right arrow`` setting).

A plain Alfred list (filterable by typing): poster, summary, release, ratings,
cast, crew, genres, files... Return (or ⌘⏎ on it) goes back to the results the
row came from.
"""

from __future__ import annotations

import os
import textwrap
from typing import Any
from urllib.parse import quote

from .. import alfred, fmt, nav, posters
from .. import details as sheets
from ..alfred import Item, Mod
from ..context import Context
from ..filters import to_text
from ..media import CLASSES, Source, title, web_url
from . import page
from .media_page import resolution

SUMMARY_WIDTH = 95
MAX_SUMMARY_ROWS = 8
MAX_CAST = 15
SEARCHABLE_PEOPLE = {"movie", "show"}  # actor / director filters exist for these libtypes


def join(*parts: object) -> str:
    """``fmt.join`` without the falsy parts (0 views, missing values...)."""
    return fmt.join(*(p for p in parts if p))


def summary_rows(text: str | None, icon: str = "document") -> list[Item]:
    """The summary cut in lines (a row shows one line), ⌘L shows it whole."""
    text = (text or "").strip()
    if not text:
        return []
    lines = textwrap.wrap(" ".join(text.split()), SUMMARY_WIDTH)
    if len(lines) > MAX_SUMMARY_ROWS:
        lines = lines[:MAX_SUMMARY_ROWS]
        lines[-1] = lines[-1].rstrip(".,;") + "…"
    rows = []
    for index, line in enumerate(lines):
        label = "📝 Summary" if index == 0 else ""
        rows.append(Item(line, f"{label} ǀ ⌘L whole summary" if label else "⌘L whole summary",
                         icon=alfred.icon(icon), text=text, match=f"summary {line}"))
    return rows


def info(title_: str, subtitle: str, icon: str = "info", text: str | None = None, intent=None) -> Item:
    return Item(title_, subtitle, intent=intent, icon=alfred.icon(icon), text=text or title_)


def _tags(media: Any, name: str) -> list[str]:
    return [t.tag for t in getattr(media, name, None) or [] if getattr(t, "tag", None)]


def _people_search(ctx: Context, kind: str, filter_name: str, name: str):
    if kind not in SEARCHABLE_PEOPLE:
        return None
    return alfred.search(to_text(ctx.store.alias, [("libtype", kind), (filter_name, name)]))


# ------------------------------------------------------------ library media
@page("more/<mid>/<key>")
def library_media(ctx: Context, mid: str, key: str) -> list[Item]:
    plex = ctx.server(mid)
    media = plex.fetchItem(int(key))
    kind = CLASSES.get(type(media).__name__, (media.type, ""))[0]
    src = Source(ctx.store.server(mid) or {}, plex)
    g = lambda name: getattr(media, name, None)  # noqa: E731
    label = title(media, kind)
    actions = alfred.browse(nav.join("media", mid, key))

    poster = posters.server_posters(ctx.settings, plex, [media]).get(str(media.ratingKey))
    header = Item(label, join(kind.capitalize(), src.server.get("friendlyName"), "⏎ all the actions"),
                  intent=actions, text=label,
                  icon=str(poster) if poster else alfred.icon(CLASSES.get(type(media).__name__, (kind, "movie"))[1]))
    if g("thumb"):
        header.quicklook = plex.url(g("thumb"), includeToken=True)
    items = [header]
    if g("tagline"):
        items.append(info(f"“{g('tagline')}”", "Tagline", "info"))
    if kind == "episode":
        items.append(info(join(g("grandparentTitle"), g("parentTitle"), g("seasonEpisode")), "Show ǀ Season ǀ Episode",
                          "show", intent=alfred.browse(nav.join("more", mid, g("grandparentRatingKey")))
                          if g("grandparentRatingKey") else None))
    items += summary_rows(g("summary"))

    counts = None
    if kind == "show":
        counts = join(fmt.plural(g("childCount"), "season"), fmt.plural(g("leafCount"), "episode"))
    elif kind in {"season", "album"}:
        counts = fmt.plural(g("leafCount"), "episode" if kind == "season" else "track")
    released = fmt.day(g("originallyAvailableAt"), ctx.settings.date_format) if g("originallyAvailableAt") else None
    facts = join(released and f"Released {released}", sheets.human_duration(g("duration")), counts,
                 g("contentRating"), g("studio"))
    if facts:
        items.append(info(facts, "Release ǀ duration ǀ content rating ǀ studio", "movie"))
    audience, critics = sheets._source(g("audienceRatingImage")), sheets._source(g("ratingImage"))
    ratings = join(
        g("audienceRating") and f"⭐ Audience {g('audienceRating')}/10 {audience}".strip(),
        g("rating") and f"Critics {g('rating')}/10 {critics}".strip(),
        g("userRating") and f"You {g('userRating')}/10",
    )
    if ratings:
        items.append(info(ratings, "Ratings", "statistics"))
    played = "✓ Played" if g("isPlayed") else ("◐ In progress" if g("viewOffset") else "Not played")
    items.append(info(join(played, g("viewCount") and fmt.plural(g("viewCount"), "view"),
                               g("lastViewedAt") and f"last viewed {fmt.ago(g('lastViewedAt'))}"),
                      join(g("addedAt") and f"Added {fmt.day(g('addedAt'), ctx.settings.date_format)}",
                               g("librarySectionTitle")), "watch"))

    for name, label_, icon in (("genres", "Genres", "genre"), ("countries", "Countries", "location"),
                               ("collections", "Collections", "collection"), ("labels", "Labels", "filter")):
        values = _tags(media, name)
        if values:
            items.append(info(", ".join(values), label_, icon))
    if g("editionTitle"):
        items.append(info(g("editionTitle"), "Edition", "info"))

    roles = list(g("roles") or [])
    for role in roles[:MAX_CAST]:
        character = getattr(role, "role", None)
        search = _people_search(ctx, kind, "actor", role.tag)
        items.append(Item(f"🎭 {role.tag}", join(character and f"as {character}",
                                                     "⏎ their medias on your servers" if search else "Cast"),
                          intent=search, icon=alfred.icon("person"), text=role.tag))
    if len(roles) > MAX_CAST:
        items.append(info(f"… and {len(roles) - MAX_CAST} more", "Cast", "people"))
    for name, label_ in (("directors", "Director"), ("writers", "Writer"), ("producers", "Producer")):
        for person in _tags(media, name)[:5]:
            search = _people_search(ctx, kind, "director", person) if name == "directors" else None
            items.append(Item(f"🎬 {person}", join(label_, "⏎ their medias on your servers" if search else None),
                              intent=search, icon=alfred.icon("person"), text=person))

    for version in g("media") or []:
        for part in version.parts:
            name = os.path.basename(part.file or "") or f"Part {part.id}"
            items.append(info(f"💾 {name}", join(fmt.size(part.size), part.container,
                                                     resolution(version.videoResolution),
                                                     version.videoCodec, version.audioCodec),
                              "document", text=part.file or name))
    ids = sheets._ids(media)
    if ids:
        items.append(info(ids, "IDs", "data"))

    try:
        sheet = alfred.details(str(sheets.prepare(ctx, plex, media, mid)))
    except Exception:  # noqa: BLE001 - the sheet is a bonus
        sheet = alfred.run("media.details", mid=mid, key=key)
    items.append(Item("📖 Full sheet", "Everything on one page (Text View) ǀ ⎋ to come back",
                      intent=sheet, icon=alfred.icon("info")))
    items.append(Item("⚙️ All the actions", "Play, mark played, rate, playlists, collections, download...",
                      intent=actions, icon=alfred.icon("setting")))
    url = web_url(media, kind)
    if url:
        items.append(Item("🌐 Open in Plex Web", url, intent=alfred.open_url(url), icon=alfred.icon("web")))
    return items


# --------------------------------------------------------------- discover
def discover_metadata(account: Any, rating_key: str) -> Any | None:
    """Full Discover metadata (XML element) of a movie / show."""
    data = account.query(f"{account.METADATA}/library/metadata/{quote(str(rating_key), safe='')}")
    if data is None:
        return None
    for element in data:
        if element.tag in {"Video", "Directory", "Metadata"}:
            return element
    return None


def _children(element: Any, tag: str) -> list[Any]:
    return list(element.iter(tag)) if element is not None else []


@page("more/discover/<uuid>/<kind>/<key>/<name>")
def discover_media(ctx: Context, uuid: str, kind: str, key: str, name: str) -> list[Item]:
    from .discover import WEB_URL, _tmdb

    account = ctx.account(uuid)
    folder = "people" if kind == "person" else "metadata"
    url = WEB_URL.format(key=quote(f"/library/{folder}/{key}", safe=""))
    if kind == "person":
        return [
            Item(name, "Person ǀ ⏎ their medias on Plex Discover", intent=alfred.discover(name),
                 icon=alfred.icon("person_discover"), text=name),
            Item("🔍 Search on your servers", name, intent=alfred.search(name), icon=alfred.icon("folder")),
            Item("🌐 Open in Plex Web", url, intent=alfred.open_url(url), icon=alfred.icon("web")),
        ]
    element = discover_metadata(account, key)
    a = (element.attrib if element is not None else {}).get
    label = f"{a('title')}{fmt.year(a('year'))}" if a("title") else name
    guid = a("guid") or ""
    thumb = posters.absolute(a("thumb"))
    poster = posters.url_posters(ctx.settings, account._session, {guid or key: thumb},
                                 {guid or key: {"title": label, "kind": kind}}).get(guid or key) if thumb else None
    find = alfred.search(nav=nav.join("search", "guid", kind, guid, label)) if guid else alfred.search(label)
    header = Item(label, join(kind.capitalize(), "Plex Discover", "⏎ find it on your servers"), intent=find,
                  icon=str(poster) if poster else alfred.icon(f"{kind}_discover"), text=label)
    if thumb:
        header.quicklook = thumb
    items = [header]
    if element is None:
        items.append(alfred.message("No more details on Plex Discover", "Try again later"))
    else:
        if a("tagline"):
            items.append(info(f"“{a('tagline')}”", "Tagline"))
        items += summary_rows(a("summary"))
        duration = sheets.human_duration(int(a("duration"))) if str(a("duration") or "").isdigit() else None
        seasons = fmt.plural(a("childCount"), "season") if kind == "show" and a("childCount") else None
        facts = join(a("originallyAvailableAt") and f"Released {a('originallyAvailableAt')}", duration, seasons,
                         a("contentRating"), a("studio"))
        if facts:
            items.append(info(facts, "Release ǀ duration ǀ content rating ǀ studio", "movie"))
        ratings = join(a("audienceRating") and f"⭐ Audience {a('audienceRating')}/10",
                           a("rating") and f"Critics {a('rating')}/10")
        if ratings:
            items.append(info(ratings, "Ratings", "statistics"))
        for tag, label_, icon in (("Genre", "Genres", "genre"), ("Country", "Countries", "location")):
            values = [e.attrib.get("tag") for e in _children(element, tag) if e.attrib.get("tag")]
            if values:
                items.append(info(", ".join(values), label_, icon))
        roles = _children(element, "Role")
        for role in roles[:MAX_CAST]:
            name = role.attrib.get("tag", "")
            items.append(Item(f"🎭 {name}", join(role.attrib.get("role") and f"as {role.attrib['role']}",
                                                    "⏎ search on Plex Discover"),
                              intent=alfred.discover(f"{name}/people"), icon=alfred.icon("person_discover"),
                              text=name))
        for tag, label_ in (("Director", "Director"), ("Writer", "Writer")):
            for person in _children(element, tag)[:5]:
                name = person.attrib.get("tag", "")
                items.append(Item(f"🎬 {name}", join(label_, "⏎ search on Plex Discover"),
                                  intent=alfred.discover(f"{name}/people"), icon=alfred.icon("person_discover"),
                                  text=name))
    items.append(Item("🔍 Find it on your servers", label, intent=find, icon=alfred.icon("folder")))
    tmdb = _tmdb({"Guid": [{"id": e.attrib.get("id", "")} for e in _children(element, "Guid")]})
    if tmdb:
        items.append(Item("🎬 Movie and TV Show Search", "Infos, cast, trailers...",
                          intent=alfred.mtv(f"{'m' if kind == 'movie' else 't'}:{tmdb}"),
                          icon=alfred.icon("movie_and_tv_show_search")))
    if guid:
        on_list = guid in ctx.watchlist(uuid)
        here = alfred.browse(nav.join("more", "discover", uuid, kind, key, name))
        items.append(Item("🔖 Remove from watchlist" if on_list else "🔖 Add to watchlist", "Your plex watchlist",
                          intent=alfred.run("watchlist", then=here, uuid=uuid, guid=guid, title=label,
                                            add=not on_list),
                          icon=alfred.icon("delete" if on_list else "add")))
    items.append(Item("🌐 Open in Plex Web", url, intent=alfred.open_url(url), icon=alfred.icon("web"),
                      mods={"cmd": Mod("Copy the link", alfred.run("clipboard", text=url, label="Link"),
                                       alfred.icon("web"))}))
    return items
