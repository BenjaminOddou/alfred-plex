"""Library browser: pick a sort and filters from lists, see the result as a list or as posters."""

from __future__ import annotations

from typing import Any

from .. import alfred, fmt, nav
from ..alfred import Intent, Item, Mod
from ..context import Context
from ..library import BOOLEAN, LibraryState, filter_label, libtype, results, search_text, total
from ..media import Source, prefetch_posters, to_item
from ..plex import parallel
from . import error_item, page


def state_of(ctx: Context) -> LibraryState:
    return LibraryState.from_dict(ctx.state)


def open_library(mid: str, key: Any, state: LibraryState, history: list[dict] | None = None) -> Intent:
    """The library in the view the user is using (list or posters).

    ``history`` makes the new library page *replace* the current one (after a
    sort / filter pick) instead of stacking on top of the pickers.
    """
    if state.view == "grid":
        intent = alfred.grid(nav.join("grid", "library", mid, key), state=state.to_dict())
    else:
        intent = alfred.browse(nav.join("library", mid, key), state=state.to_dict())
    if history is not None:
        intent.variables["back"] = alfred.history_json(history)
    return intent


def library_history(ctx: Context, pickers: int) -> list[dict]:
    """History of the library page, ``pickers`` pages below the current one."""
    return ctx.history[: len(ctx.history) - pickers] if pickers else ctx.history


def _section(ctx: Context, mid: str, key: str):
    plex = ctx.server(mid)
    return plex, plex.library.sectionByID(int(key))


@page("library")
def libraries(ctx: Context) -> list[Item]:
    saved = ctx.store.servers.items
    if not saved:
        return [alfred.message("No plex media server detected", "Press ⏎ and sign in with Plex",
                               alfred.browse("accounts/new"))]
    found = parallel(lambda s: (s, ctx.server(s["machineIdentifier"]).library.sections()), saved)
    items = []
    for result in found:
        if isinstance(result, Exception):
            items.append(error_item(result))
            continue
        server, sections = result
        mid = server["machineIdentifier"]
        grid_first = ctx.settings.grid_view
        for section in sections:
            list_state, grid_state = LibraryState(), LibraryState(view="grid")
            first, other = (grid_state, list_state) if grid_first else (list_state, grid_state)
            items.append(Item(
                section.title,
                fmt.join(server.get("friendlyName"), section.type,
                         "⏎ posters ǀ ⌘⏎ list" if grid_first else "⏎ browse ǀ ⌘⏎ posters"),
                intent=open_library(mid, section.key, first),
                icon=alfred.icon(section.type if section.type in {"movie", "show", "artist", "photo"} else "library"),
                mods={"cmd": Mod("Show this library as a list" if grid_first else "Show this library as posters",
                                 open_library(mid, section.key, other),
                                 alfred.icon("library" if grid_first else "photo"))},
            ))
    return items


@page("library/<mid>/<key>")
def library(ctx: Context, mid: str, key: str) -> list[Item]:
    plex, section = _section(ctx, mid, key)
    state = state_of(ctx).replace(view="list")
    here = open_library(mid, key, state)
    sorts = {s.key: s.title for s in section.listSorts(libtype=libtype(section))}
    count = total(section, state)
    query = search_text(ctx.store.alias, section, state)
    items = [
        alfred.message(f"{section.title}: {fmt.plural(count, libtype(section))}",
                       fmt.join(plex.friendlyName, f"Sort: {state.sort_label(sorts)}",
                                f"Filters: {state.filters_label()}"), icon_name=section.type),
        Item("🖼️ Show as posters", f"Grid of {fmt.plural(min(count, ctx.settings.limit * 4), 'poster')}",
             intent=open_library(mid, key, state.replace(view="grid")), icon=alfred.icon("photo")),
        Item(f"↕️ Sort: {state.sort_label(sorts)}", "Choose another order",
             intent=alfred.browse(nav.join("library", mid, key, "sort"), state=state.to_dict()),
             icon=alfred.icon("sort")),
        Item("➕ Add a filter", "Genre, year, resolution, unplayed, collection, actor...",
             intent=alfred.browse(nav.join("library", mid, key, "filter"), state=state.to_dict()),
             icon=alfred.icon("filter")),
    ]
    for name in state.filters:
        items.append(Item(f"✖ {state.labels.get(name, name)}", "Remove this filter",
                          intent=open_library(mid, key, state.without(name), ctx.history), icon=alfred.icon("delete")))
    if len(state.filters) > 1:
        items.append(Item("🧹 Clear all filters", "Show the whole library",
                          intent=open_library(mid, key, state.cleared(), ctx.history), icon=alfred.icon("delete")))
    items += [
        Item("🔍 Open in Plex Search", query, intent=alfred.search(query), icon=alfred.icon("folder"), text=query),
        Item("💾 Save as a preset", f"{query} ǀ ⏎ then type a title",
             intent=alfred.ask("Preset Title/Subtitle", f"Save '{query}'", "preset.save", then=here, value=query),
             icon=alfred.icon("preset")),
    ]
    src = Source(ctx.store.server(mid) or {}, plex)
    watchlist = ctx.watchlist(src.account_uuid) if src.account_uuid else set()
    medias = results(section, state, ctx.settings.limit * 2)
    prefetch_posters(ctx, [(src, media) for media in medias])
    for media in medias:
        row = to_item(ctx, src, media, watchlist, here)
        if row:
            items.append(row)
    return items


@page("library/<mid>/<key>/sort")
def sort(ctx: Context, mid: str, key: str) -> list[Item]:
    _, section = _section(ctx, mid, key)
    state = state_of(ctx)
    items = []
    for option in section.listSorts(libtype=libtype(section)):
        first = option.defaultDirection or "asc"
        other = "desc" if first == "asc" else "asc"
        current = state.sort_field == option.key
        arrows = {"asc": "↑ ascending", "desc": "↓ descending"}
        items.append(Item(
            f"{'✓ ' if current else ''}{option.title}",
            f"⏎ {arrows[first]} ǀ ⌘⏎ {arrows[other]}",
            intent=open_library(mid, key, state.replace(sort=f"{option.key}:{first}"), library_history(ctx, 1)),
            icon=alfred.icon("sort"),
            mods={"cmd": Mod(f"Sort by {option.title}, {arrows[other]}",
                             open_library(mid, key, state.replace(sort=f"{option.key}:{other}"),
                                          library_history(ctx, 1)), alfred.icon("sort"))},
        ))
    return items


@page("library/<mid>/<key>/filter")
def filters(ctx: Context, mid: str, key: str) -> list[Item]:
    _, section = _section(ctx, mid, key)
    state = state_of(ctx)
    items = []
    for option in section.listFilters(libtype=libtype(section)):
        active = option.filter in state.filters
        if option.filterType == BOOLEAN:
            changed = state.without(option.filter) if active else state.with_filter(
                option.filter, 1, filter_label(option.title, "", BOOLEAN))
            items.append(Item(f"{'✓ ' if active else ''}{option.title}",
                              "⏎ remove this filter" if active else "⏎ only show these items",
                              intent=open_library(mid, key, changed, library_history(ctx, 1)),
                              icon=alfred.icon("filter")))
        else:
            current = state.labels.get(option.filter, "")
            items.append(Item(f"{'✓ ' if active else ''}{option.title}",
                              current or f"Choose a {option.title.lower()}",
                              intent=alfred.browse(nav.join("library", mid, key, "filter", option.filter),
                                                   state=state.to_dict()),
                              icon=alfred.icon("filter"), match=option.title))
    return items


@page("library/<mid>/<key>/filter/<name>")
def filter_choices(ctx: Context, mid: str, key: str, name: str) -> list[Item]:
    _, section = _section(ctx, mid, key)
    state = state_of(ctx)
    option = next((f for f in section.listFilters(libtype=libtype(section)) if f.filter == name), None)
    title = option.title if option else name
    items = []
    if name in state.filters:
        items.append(Item(f"✖ Remove {state.labels.get(name, name)}", "Show every value again",
                          intent=open_library(mid, key, state.without(name), library_history(ctx, 2)),
                          icon=alfred.icon("delete")))
    for choice in section.listFilterChoices(name, libtype=libtype(section))[:1000]:
        items.append(Item(choice.title, f"⏎ {title}: {choice.title}",
                          intent=open_library(mid, key, state.with_filter(
                              name, choice.key, filter_label(title, choice.title, "string")), library_history(ctx, 2)),
                          icon=alfred.icon("filter")))
    return items
