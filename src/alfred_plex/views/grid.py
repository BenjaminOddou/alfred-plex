"""Posters in Alfred's Grid View (Alfred 5.5+).

``python3 main.py grid`` renders one of these pages; the selected tile goes
back to the Router like a Script Filter row (⏎ opens the media actions page or
the children of a show / season / album / collection, ⌘⏎ the actions page,
⌥⏎ the full details sheet).
"""

from __future__ import annotations

from typing import Any

from .. import alfred, filters, fmt, nav, posters
from ..alfred import Feedback, Intent, Item, Mod
from ..context import Context
from ..details import human_duration
from ..library import LibraryState, libtype, results, search_text
from ..media import CLASSES, PLAYABLE_STATE, TAGS, Source, nested_search, title, to_item
from . import error_item, remember_page

router = nav.Router()
page = router.page

CONTAINERS = {"show", "season", "artist", "album", "collection", "playlist"}
RESOLUTIONS = {"4k": "4K", "1080": "1080p", "720": "720p", "480": "480p", "576": "576p", "sd": "SD"}


def grid_details(media: Any, kind: str) -> str:
    """Footer of the selected tile: the useful facts at a glance."""
    g = lambda name: getattr(media, name, None)  # noqa: E731
    version = (g("media") or [None])[0]
    resolution = RESOLUTIONS.get(str(getattr(version, "videoResolution", "") or "").lower())
    played = "✓ played" if g("isPlayed") else ("◐ in progress" if g("viewOffset") else None)
    counts = None
    if kind == "show":
        counts = fmt.join(fmt.plural(g("childCount"), "season"), fmt.plural(g("leafCount"), "episode"))
    elif kind in {"season", "album"}:
        counts = fmt.plural(g("leafCount"), "episode" if kind == "season" else "track")
    elif kind in {"collection", "playlist"}:
        counts = fmt.plural(g("childCount") or g("leafCount"), "item")
    rating = g("audienceRating") or g("rating")
    return fmt.join(g("year"), human_duration(g("duration")) if kind in {"movie", "episode"} else None, counts,
                    rating and f"⭐ {rating}", g("contentRating"), resolution, played)


def as_grid(intent: Intent | None) -> Intent | None:
    """A Plex Search with a query opens its results as posters too (same action as the list, in the grid)."""
    if intent is None or intent.action != "search" or not intent.arg or intent.variables.get("nav") != "search":
        return intent
    return alfred.grid("grid/search", state={"query": intent.arg})


def tile(ctx: Context, src: Source, media: Any, poster: Any, here: Intent, watchlist: set[str]) -> Item | None:
    """Same row as the list (every shortcut, the → action, Quick Look), with the poster and a footer."""
    kind, image = CLASSES.get(type(media).__name__, (None, None))
    if kind is None:
        return None
    item = to_item(ctx, src, media, watchlist, here)
    if item is None:
        return None
    if kind not in TAGS:
        item.subtitle = grid_details(media, kind)
        if getattr(media, "isPlayed", None) and kind in PLAYABLE_STATE and "✓" not in item.subtitle:
            item.subtitle = fmt.join(item.subtitle, "✓ played")
    item.icon = str(poster) if poster else alfred.icon(image)
    item.intent = as_grid(item.intent)
    for mod in item.mods.values():
        mod.intent = as_grid(mod.intent)
    item.match = fmt.join(item.title, kind, getattr(media, "year", None), src.server.get("friendlyName"),
                          *(t.tag for t in (getattr(media, "genres", None) or [])[:4]))
    return item


def tiles(ctx: Context, src: Source, medias: list[Any], here: Intent, watchlist: set[str] | None = None) -> list[Item]:
    if watchlist is None:
        watchlist = ctx.watchlist(src.account_uuid) if src.account_uuid else set()
    found = posters.server_posters(ctx.settings, src.plex, [m for m in medias if getattr(m, "ratingKey", None)])
    rows = [tile(ctx, src, media, found.get(str(getattr(media, "ratingKey", ""))), here, watchlist)
            for media in medias]
    return [row for row in rows if row]


def list_tile(target: Intent, subtitle: str) -> Item:
    return Item("☰ List view", subtitle, intent=target, icon=alfred.icon("library"))


def return_tile(target: Intent, where: str) -> Item:
    return Item("Return", f"Back to {where}", intent=target, icon=alfred.icon("return"))


def _source(ctx: Context, mid: str) -> Source:
    return Source(ctx.store.server(mid) or {}, ctx.server(mid))


def _here(ctx: Context) -> Intent:
    return alfred.grid(ctx.nav, state=ctx.state or None)


def _limit(ctx: Context) -> int:
    return ctx.settings.limit * 4


# ------------------------------------------------------------------- pages
@page("grid/library/<mid>/<key>")
def library(ctx: Context, mid: str, key: str) -> list[Item]:
    from .library import open_library

    src = _source(ctx, mid)
    section = src.plex.library.sectionByID(int(key))
    state = LibraryState.from_dict(ctx.state).replace(view="grid")
    here = _here(ctx)
    sorts = {s.key: s.title for s in section.listSorts(libtype=libtype(section))}
    items = [
        Item(f"↕️ {state.sort_label(sorts)}", f"{section.title}: change the order",
             intent=alfred.browse(nav.join("library", mid, key, "sort"), state=state.to_dict()),
             icon=alfred.icon("sort")),
        Item("➕ Filter", f"Filters: {state.filters_label()}",
             intent=alfred.browse(nav.join("library", mid, key, "filter"), state=state.to_dict()),
             icon=alfred.icon("filter")),
    ]
    items += [Item(f"✖ {state.labels.get(name, name)}", "Remove this filter",
                   intent=open_library(mid, key, state.without(name), ctx.history), icon=alfred.icon("delete"))
              for name in state.filters]
    items.append(list_tile(open_library(mid, key, state.replace(view="list"), ctx.history),
                           "Same library as a list"))
    query = search_text(ctx.store.alias, section, state)
    items += [
        Item("🔍 Open in Plex Search", query, intent=alfred.search(query), icon=alfred.icon("folder"), text=query),
        Item("💾 Save as a preset", f"{query} ǀ ⏎ then type a title",
             intent=alfred.ask("Preset Title/Subtitle", f"Save '{query}'", "preset.save", then=here, value=query),
             icon=alfred.icon("preset")),
    ]
    return items + tiles(ctx, src, results(section, state, _limit(ctx)), here)


@page("grid/recent/<mid>")
def recent(ctx: Context, mid: str) -> list[Item]:
    src = _source(ctx, mid)
    return [list_tile(alfred.browse(nav.join("servers", mid, "recent")), "Recently added as a list"),
            *tiles(ctx, src, src.plex.library.recentlyAdded()[: _limit(ctx)], _here(ctx))]


@page("grid/continue/<mid>")
def continue_watching(ctx: Context, mid: str) -> list[Item]:
    src = _source(ctx, mid)
    return [list_tile(alfred.browse(nav.join("servers", mid, "continue")), "Continue watching as a list"),
            *tiles(ctx, src, src.plex.continueWatching(), _here(ctx))]


@page("grid/children/<mid>/<key>")
def children(ctx: Context, mid: str, key: str) -> list[Item]:
    src = _source(ctx, mid)
    parent = src.plex.fetchItem(int(key))
    kind = CLASSES.get(type(parent).__name__, (parent.type, ""))[0]
    found = {"show": "seasons", "season": "episodes", "artist": "albums", "album": "tracks"}.get(kind)
    medias = getattr(parent, found)() if found else parent.items()
    header = Item(title(parent, kind), "⏎ all the actions on it",
                  intent=alfred.browse(nav.join("media", mid, key)),
                  icon=alfred.icon("setting"))
    items = [header]
    nested = nested_search(ctx, parent, kind)
    if nested:
        items.append(list_tile(nested, "The same content as a list (Plex Search)"))
    return [*items, *tiles(ctx, src, medias, _here(ctx))]


@page("grid/search")
def search(ctx: Context) -> list[Item]:
    from .search import _library_search, collect, finder_for, save_preset_item

    text = ctx.state.get("query", "")
    if text:
        query = filters.parse(text, ctx.store.alias)
        found, items = collect(ctx, query, finder_for(query))
    else:
        found, items = collect(ctx, filters.default_view(ctx.settings.default_view), _library_search)
    here = _here(ctx)
    items = [
        Item(f"🔍 {'Edit the search' if text else 'Search'}",
             f"{text} ǀ type, live results as a list" if text else "Type, live results as a list",
             intent=alfred.search(text), icon=alfred.icon("folder"), text=text or None),
        *([save_preset_item(text, then=here)] if text else []),
        *items,
    ]
    by_source: dict[str, tuple[Source, list[Any], set[str]]] = {}
    for src, media, watchlist in found:
        by_source.setdefault(src.machine_id, (src, [], watchlist))[1].append(media)
    for src, medias, watchlist in by_source.values():
        items += tiles(ctx, src, medias, here, watchlist)
    return items


@page("grid/discover")
def discover(ctx: Context) -> list[Item]:
    """Discover as posters: same shortcuts as the list (⌘ web, ⌃ infos, ⇧ watchlist...)."""
    from .discover import meta_key, poster_icons, results_and_watchlist
    from .discover import to_item as discover_item

    saved = ctx.default_account()
    if not saved:
        return [alfred.message("No plex account connected", "Sign in with Plex first", alfred.browse("accounts/new"))]
    uuid = saved["uuid"]
    account = ctx.account(uuid)
    metas, watchlist = results_and_watchlist(ctx, account, uuid, ctx.state.get("query", ""))
    images = poster_icons(ctx, account, metas)
    here = _here(ctx)
    text = ctx.state.get("query", "")
    items = [Item(f"🔍 {'Edit the search' if text else 'Search'}",
                  f"{text} ǀ type, live results as a list" if text else "Type, live results as a list",
                  intent=alfred.discover(text), icon=alfred.icon("discover"), text=text or None)]
    for meta in metas:
        item = discover_item(ctx, uuid, meta, watchlist, here)
        if item is None:
            continue
        poster = images.get(meta_key(meta))
        if poster:
            item.icon = str(poster)
        item.subtitle = fmt.join(meta.get("type"), meta.get("year"), meta.get("contentRating"),
                                 meta.get("audienceRating") and f"⭐ {meta.get('audienceRating')}")
        items.append(item)
    return items


@page("grid/watchlist/<uuid>")
def watchlist(ctx: Context, uuid: str) -> list[Item]:
    account = ctx.account(uuid)
    medias = account.watchlist()
    images = posters.url_posters(ctx.settings, account._session, {m.guid: getattr(m, "thumb", "") for m in medias},
                                 {m.guid: {"title": f"{m.title}{fmt.year(m.year)}", "kind": m.type} for m in medias})
    here = _here(ctx)
    items = [list_tile(alfred.browse(nav.join("accounts", uuid, "watchlist")), "Your watchlist as a list")]
    for media in medias:
        label = f"{media.title}{fmt.year(media.year)}"
        poster = images.get(media.guid)
        items.append(Item(
            label, fmt.join(media.type, getattr(media, "contentRating", None), "⏎ find it on your servers"),
            intent=alfred.search(nav=nav.join("search", "guid", media.type, media.guid, label)),
            icon=str(poster) if poster else alfred.icon(f"{media.type}_discover_bookmarked"), text=label,
            mods={"cmd": Mod("Remove from your watchlist", alfred.run(
                "watchlist", then=here, uuid=uuid, guid=media.guid, title=label, add=False), alfred.icon("delete"))},
        ))
    return items


# ----------------------------------------------------------------- render
def default_back(ctx: Context) -> Intent:
    """Where Return goes when the grid was opened without history."""
    parts = nav.split(ctx.nav)
    if parts[1:2] == ["library"]:
        return alfred.search()
    if parts[1:2] in (["recent"], ["continue"], ["children"]) and len(parts) > 2:
        return alfred.browse(nav.join("servers", parts[2]))
    if parts[1:2] == ["watchlist"] and len(parts) > 2:
        return alfred.browse(nav.join("accounts", parts[2], "watchlist"))
    if parts[1:2] == ["discover"]:
        return alfred.discover(ctx.state.get("query", ""))
    if parts[1:2] == ["search"]:
        return alfred.search(ctx.state.get("query", ""))
    return alfred.browse("")


def render_grid(ctx: Context) -> Feedback:
    from . import describe

    feedback = Feedback()
    target = alfred.pop(ctx.history) or default_back(ctx)
    target.variables.setdefault("back", "[]")
    feedback.add(return_tile(target, describe(ctx, target)))
    resolved = router.resolve(ctx.nav)
    if resolved is None:
        return feedback.add(alfred.message("Unknown grid page", ctx.nav))
    handler, params = resolved
    try:
        items = handler(ctx, **params)
    except Exception as error:  # noqa: BLE001 - always answer Alfred
        from ..system import log

        log.exception("Grid %s failed", ctx.nav)
        items = [error_item(error)]
    feedback.extend(items)
    if len(feedback.items) == 1:
        feedback.add(alfred.message("Nothing to show", "No media here yet"))
    alfred.link(feedback.items, _here(ctx), ctx.history)
    remember_page(ctx, _here(ctx), feedback.items)
    return feedback.dedupe()
