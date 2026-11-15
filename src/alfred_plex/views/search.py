"""Plex Search: live search on every saved server, in parallel."""

from __future__ import annotations

from typing import Any

from .. import alfred, filters, fmt, nav
from ..alfred import Feedback, Intent, Item
from ..context import Context
from ..media import Source, to_item
from ..plex import parallel
from . import back_item, error_item


def _sources(ctx: Context, query: filters.SearchQuery) -> tuple[list[Source], list[Item]]:
    servers = [s for s in ctx.store.servers.items if query.accepts_server(s.get("friendlyName", ""))]
    results = parallel(lambda s: Source(s, ctx.server(s["machineIdentifier"])), servers)
    sources = [r for r in results if isinstance(r, Source)]
    errors = [error_item(r) for r in results if isinstance(r, Exception)]
    return sources, errors


def _library_search(ctx: Context, src: Source, query: filters.SearchQuery) -> list[Any]:
    """Run the filters on every matching section of one server (sections in parallel)."""
    sections = [s for s in src.plex.library.sections() if query.accepts_section(s.title, s.type)]
    kwargs = query.search_kwargs(ctx.settings.limit)
    found = parallel(lambda section: section.search(**kwargs), sections, workers=4)
    errors = [r for r in found if isinstance(r, Exception)]
    if errors and len(errors) == len(found):
        raise errors[0]
    return [media for result in found if not isinstance(result, Exception) for media in result]


def _hub_search(ctx: Context, src: Source, query: filters.SearchQuery) -> list[Any]:
    return src.plex.search(query.text, mediatype=query.mediatype, limit=ctx.settings.limit)


def _keep(media: Any, query: filters.SearchQuery, watchlist: set[str]) -> bool:
    if query.watchlist is None:
        return True
    return (getattr(media, "guid", None) in watchlist) == bool(query.watchlist)


def collect(ctx: Context, query: filters.SearchQuery, finder) -> tuple[list[tuple[Source, Any, set[str]]], list[Item]]:
    """Search every server in parallel: ``[(source, media, watchlist)]`` + error rows."""
    sources, errors = _sources(ctx, query)
    watchlists: dict[str, set[str]] = {}
    for src in sources:
        if src.account_uuid and src.account_uuid not in watchlists:
            watchlists[src.account_uuid] = ctx.watchlist(src.account_uuid)

    results = parallel(lambda src: (src, finder(ctx, src, query)), sources)
    found = []
    for result in results:
        if isinstance(result, Exception):
            continue
        src, medias = result
        watchlist = watchlists.get(src.account_uuid, set())
        found += [(src, media, watchlist) for media in medias if _keep(media, query, watchlist)]
    if all(isinstance(r, Exception) for r in results) and results:
        raise results[0]
    return found, errors


def run_search(ctx: Context, query: filters.SearchQuery, finder, here: Intent) -> list[Item]:
    found, items = collect(ctx, query, finder)
    for src, media, watchlist in found:
        item = to_item(ctx, src, media, watchlist, here)
        if item:
            items.append(item)
    return items


def finder_for(query: filters.SearchQuery):
    return _library_search if query.is_filter else _hub_search


def _streams(ctx: Context, mid: str, rating_key: str) -> list[Item]:
    plex = ctx.server(mid)
    media = plex.fetchItem(int(rating_key))
    kind = media.type
    items = []
    for m_index, version in enumerate(media.media):
        for p_index, part in enumerate(version.parts):
            video = part.videoStreams()
            items.append(Item(
                video[0].displayTitle if video else f"Version {m_index + 1}",
                fmt.join(
                    f"Audio(s): {', '.join(a.displayTitle for a in part.audioStreams())}",
                    f"Subtitle(s): {', '.join(s.displayTitle for s in part.subtitleStreams())}",
                    fmt.size(part.size),
                ),
                intent=alfred.run("stream", mid=mid, key=media.key, type=kind, media=m_index, part=p_index),
                icon=alfred.icon(kind),
            ))
    return items


def _guid(ctx: Context, libtype: str, guid: str, title: str, here: Intent) -> list[Item]:
    def finder(ctx: Context, src: Source, query) -> list[Any]:
        # One request per server (v2 queried every section one by one).
        return src.plex.library.search(guid=guid, libtype=libtype, maxresults=ctx.settings.limit)

    items = run_search(ctx, filters.SearchQuery(), finder, here)
    return items or [alfred.message(f"'{title}' is not on your servers", "Try to search something else")]


def libraries(ctx: Context) -> list[Item]:
    """Empty search = your libraries (merged "Plex Libraries"): browse, sort, filter, posters."""
    from .library import libraries as library_rows

    return [row for row in library_rows(ctx) if row.title != "Return"]


def render_search(ctx: Context) -> Feedback:
    feedback = Feedback()
    parts = nav.split(ctx.nav)
    here = alfred.search(ctx.query, nav=ctx.nav or "search")
    if not ctx.store.servers.items:
        feedback.add(back_item(ctx), alfred.message(
            "No plex media server detected", "Press ⏎ and sign in with Plex", alfred.browse("accounts/new")))
        alfred.link(feedback.items, here, ctx.history)
        return feedback
    try:
        if len(parts) == 4 and parts[1] == "streams":
            feedback.add(back_item(ctx, alfred.search()))
            feedback.extend(_streams(ctx, parts[2], parts[3]))
        elif len(parts) == 5 and parts[1] == "guid":
            feedback.add(back_item(ctx, alfred.search()))
            feedback.extend(_guid(ctx, parts[2], parts[3], parts[4], here))
        elif not ctx.query:
            feedback.add(back_item(ctx))
            feedback.extend(libraries(ctx))
            query = filters.default_view(ctx.settings.default_view)
            feedback.extend(run_search(ctx, query, _library_search, here)).dedupe()
        else:
            _typed(ctx, feedback, here)
            # While typing, ⏎ must open the first result: Return goes last.
            feedback.add(back_item(ctx))
    except Exception as error:  # noqa: BLE001 - always answer Alfred
        from ..system import log

        log.exception("Search failed")
        feedback.add(_invalid(ctx, f"Invalid filters: {error}") if "=" in ctx.query else error_item(error),
                     back_item(ctx))
    alfred.link(feedback.items, here, ctx.history)
    return feedback


def _typed(ctx: Context, feedback: Feedback, here: Intent) -> None:
    try:
        query = filters.parse(ctx.query, ctx.store.alias)
    except filters.FilterError as error:
        feedback.add(_invalid(ctx, f"Invalid filters: {error}"))
        return
    feedback.extend(run_search(ctx, query, finder_for(query), here)).dedupe()
    if not feedback.items:
        feedback.add(_invalid(ctx, "No media found for these filters") if query.is_filter
                     else alfred.message(f"No media found for '{ctx.query}'", "Try to search something else"))
        return
    feedback.add(Item("🖼️ Show as posters", f"These results in Alfred's Grid View ǀ {ctx.query}",
                      intent=alfred.grid("grid/search", state={"query": ctx.query}), icon=alfred.icon("photo")),
                 save_preset_item(ctx.query))


def save_preset_item(query: str) -> Item:
    """Last row of the results: keep this search for later in Plex Presets."""
    return Item(
        "💾 Save this search as a preset",
        f"{query} ǀ ⏎ then type a title (and an optional '/subtitle')",
        intent=alfred.ask("Preset Title/Subtitle", f"Save '{query}' ǀ Example: My movies/Some description",
                          "preset.save", then=alfred.search(query), value=query),
        icon=alfred.icon("preset"),
    )


def _invalid(ctx: Context, title: str) -> Item:
    mode = "activated" if ctx.store.alias.enabled else "deactivated"
    return alfred.message(
        title,
        f"Press ⏎ to see available options. Alias are {mode}",
        alfred.browse("help/alias"),
    )
