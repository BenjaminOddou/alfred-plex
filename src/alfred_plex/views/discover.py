"""Plex Discover: live search on plex.tv (movies, shows and people)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from .. import alfred, fmt, nav
from ..alfred import Feedback, Intent, Item
from ..context import Context
from ..media import attach
from ..plex import discover_json
from . import back_item, error_item

SEARCH_TYPES = {"movie": "movies", "show": "tv", "people": "people", "person": "people"}
WEB_URL = "https://app.plex.tv/desktop/#!/provider/tv.plex.provider.discover/details?key={key}&context=search"


def _title(meta: dict) -> str:
    if meta.get("type") == "person":
        return meta.get("title", "")
    return f"{meta.get('title', '')}{fmt.year(meta.get('year'))}"


def _subtitle(meta: dict) -> str:
    kind = meta.get("type")
    if kind == "movie":
        return fmt.join(kind, fmt.duration(meta.get("duration")) or "Unknown duration")
    if kind == "show":
        return fmt.join(kind, fmt.plural(meta.get("childCount"), "season"))
    return kind or ""


def _tmdb(meta: dict) -> str | None:
    for guid in meta.get("Guid") or []:
        value = str(guid.get("id", "")) if isinstance(guid, dict) else ""
        if value.startswith("tmdb://"):
            return value.split("://", 1)[1]
    return None


def to_item(ctx: Context, uuid: str, meta: dict, watchlist: set[str], here: Intent) -> Item | None:
    kind = meta.get("type")
    if kind not in {"movie", "show", "person"}:
        return None
    keys = ctx.settings.shortcuts
    label = _title(meta)
    rating_key = meta.get("ratingKey") or meta.get("metadataId") or meta.get("id") or ""
    guid = meta.get("guid", "")
    on_list = guid in watchlist
    item = Item(label, _subtitle(meta), icon=alfred.icon(f"{kind}_discover{'_bookmarked' if on_list else ''}"),
                text=label)
    if meta.get("thumb", "").startswith("http"):
        item.quicklook = meta["thumb"]

    folder = "people" if kind == "person" else "metadata"
    url = WEB_URL.format(key=quote(f"/library/{folder}/{rating_key}", safe=""))
    attach(item, keys.web, alfred.open_url(url), "Press ⏎ to open the media in plex web", "web")

    if kind == "person":
        nested = alfred.search(meta.get("title", ""))
    else:
        nested = alfred.search(nav=nav.join("search", "guid", kind, guid, label))
    attach(item, keys.nested_search, nested, "Press ⏎ to search it on your servers", "folder")

    if kind in {"movie", "show"} and guid:
        tmdb = _tmdb(meta)
        prefix = "m" if kind == "movie" else "t"
        mtv = alfred.mtv(f"{prefix}:{tmdb}") if tmdb else alfred.run("mtv", uuid=uuid, type=kind, key=rating_key)
        attach(item, keys.mtv, mtv, "Press ⏎ to get media infos using Movie and TV Show Search workflow",
               "movie_and_tv_show_search")
        action = "remove" if on_list else "add"
        attach(item, keys.watchlist,
               alfred.run("watchlist", then=here, uuid=uuid, guid=guid, title=label, add=not on_list),
               f"Press ⏎ to {action} the {kind} {'from' if on_list else 'to'} your watchlist",
               "delete" if on_list else "add")
    return item


def _results(ctx: Context, account: Any, query: str) -> list[dict]:
    language = ctx.settings.language
    if not query:
        data = discover_json(account, "/hubs/sections/home/top_watchlisted",
                             **{"X-Plex-Container-Size": ctx.settings.limit, "X-Plex-Language": language})
        return data.get("MediaContainer", {}).get("Metadata", [])

    text, _, kind = query.rpartition("/")
    if not (text and kind.strip().lower() in SEARCH_TYPES):
        text, kind = query, ""
    data = discover_json(
        account, "/library/search",
        query=text.strip(),
        limit=ctx.settings.limit,
        searchTypes=SEARCH_TYPES.get(kind.strip().lower(), "movies,tv,people"),
        searchProviders="discover",
        includeMetadata=1,
        filterPeople=1,
        **{"X-Plex-Language": language},
    )
    results = []
    for group in data.get("MediaContainer", {}).get("SearchResults", []):
        if group.get("id") in {"external", "people"}:
            for result in group.get("SearchResult", []):
                meta = result.get("Metadata") or result.get("Directory")
                if meta:
                    results.append(meta)
    return results


def posters_item(query: str) -> Item:
    return Item("🖼️ Show as posters", f"Discover {'results' if query else 'trending'} in Alfred's Grid View",
                intent=alfred.grid("grid/discover", state={"query": query}), icon=alfred.icon("photo"))


def render_discover(ctx: Context) -> Feedback:
    feedback = Feedback()
    here = alfred.discover(ctx.query)
    if not ctx.query:  # empty: Return first, typing: Return last (⏎ must open the first result)
        feedback.add(back_item(ctx))
    saved = ctx.default_account()
    if not saved:
        feedback.add(alfred.message("No plex account connected", "Press ⏎ and sign in with Plex",
                                    alfred.browse("accounts/new")))
    else:
        _results_rows(ctx, feedback, saved["uuid"], here)
    if ctx.query:
        feedback.add(back_item(ctx))
    alfred.link(feedback.items, here, ctx.history)
    return feedback.dedupe()


def _results_rows(ctx: Context, feedback: Feedback, uuid: str, here: Intent) -> None:
    rows = []
    try:
        account = ctx.account(uuid)
        watchlist = ctx.watchlist(uuid)
        for meta in _results(ctx, account, ctx.query):
            item = to_item(ctx, uuid, meta, watchlist, here)
            if item:
                rows.append(item)
    except Exception as error:  # noqa: BLE001 - always answer Alfred
        from ..system import log

        log.exception("Discover failed")
        feedback.add(error_item(error))
        return
    if not rows:
        feedback.add(alfred.message(f"No media found for '{ctx.query}'", "Try to search something else"))
    elif ctx.query:
        feedback.extend(rows).add(posters_item(ctx.query))
    else:  # trending: posters are the nicest way to look at it
        feedback.add(posters_item("")).extend(rows)
