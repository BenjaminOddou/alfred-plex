"""Plex Help pages: filters & sorts, alias, cache, data, links."""

from __future__ import annotations

import time
from urllib.parse import unquote

from .. import alfred, fmt, nav, posters
from ..alfred import Item
from ..context import Context
from ..filters import to_text
from ..plex import parallel
from . import page

LINKS = (
    ("GitHub", "https://github.com/BenjaminOddou/alfred-plex", "github"),
    ("Alfred Gallery", "https://alfred.app/workflows/benjaminoddou/plex", "alfred"),
    ("Python-PlexAPI documentation", "https://python-plexapi.readthedocs.io/en/latest/", "web"),
)


@page("help")
def help_menu(ctx: Context) -> list[Item]:
    entries = (
        ("Getting Started", "What you can do with this workflow, step by step", "start", "help"),
        ("Keyboard Shortcuts", "All the shortcuts and keywords, and how to change them", "shortcuts", "key"),
        ("Filters & Sort Options", "Filters and sort options for your plex media server(s)", "filters", "filter"),
        ("Filter Alias", "Manage filter alias file", "alias", "alias"),
        ("Workflow Cache & Logs", "Cache files, logs and logs export for a bug report", "cache", "document"),
        ("Workflow Data", "Manage workflow's data files", "data", "data"),
        ("Useful Links", "List of useful links for this workflow", "links", "web"),
    )
    return [Item(t, s, intent=alfred.browse(nav.join("help", p)), icon=alfred.icon(i)) for t, s, p, i in entries]


@page("help/start")
def getting_started(ctx: Context) -> list[Item]:
    keys = ctx.settings.shortcuts
    signed_in = bool(ctx.store.accounts.items)
    steps = [
        ("1. Sign in with Plex" + (" ✓" if signed_in else ""),
         "Your servers are added automatically" if not signed_in else "Done! Manage your accounts here",
         alfred.run("account.oauth", then=alfred.browse("")) if not signed_in else alfred.browse("accounts"),
         "people"),
        ("2. Search your medias", "Type a title, or filters such as lt=movie/ge=action",
         alfred.search(), "folder"),
        ("2b. Browse your libraries as posters", "Open Plex Search without typing: pick a library, sort and "
         "filter it, ⌘⏎ for posters", alfred.search(), "library"),
        ("3. ⏎ on a movie or an episode", "Opens all its actions: play, mark played, rate, playlist, files, "
         f"download... ({alfred.key_label(keys.actions)} on any media)", None, "setting"),
        ("4. Save your searches", "The last row of Plex Search saves it as a preset", alfred.browse("presets"),
         "preset"),
        ("5. Manage your servers", "Sessions, recently added, statistics, settings, maintenance",
         alfred.browse("servers"), "servers"),
        ("6. Export to CSV", "Libraries, history, statistics, devices, watchlist... in your downloads folder",
         None, "download"),
        ("7. Learn the shortcuts", "Every shortcut can be changed in the workflow configuration",
         alfred.browse("help/shortcuts"), "key"),
    ]
    return [Item(t, s, intent=i, icon=alfred.icon(icon)) for t, s, i, icon in steps]


def arrow_label(ctx: Context) -> str:
    from .arrow import label

    return label(ctx)


@page("help/shortcuts")
def shortcuts(ctx: Context) -> list[Item]:
    keys = ctx.settings.shortcuts
    where = "Change it in Alfred › Workflows › Plex › Configure Workflow"
    items = [alfred.message(f"Keyword {ctx.var('trigger') or 'plex'}: main menu", where, icon_name="key")]
    for _, name, _, label in keys.FIELDS:
        items.append(alfred.message(f"{alfred.key_label(getattr(keys, name))}  {label}", f"On medias ǀ {where}",
                                    icon_name="key"))
    fixed = (
        ("⏎ on a media", "Opens its actions page when ⏎ has no other action"),
        ("→ then ↩ on Plex", f"On a media: {arrow_label(ctx)} (➡️ Right arrow setting)"),
        ("⌘⏎ on Return", "Back to the main menu"),
        ("⇧ / ⌘Y", "Quick Look: poster of a media, web pages"),
        ("⌘C / ⌘L", "Copy / show in large type the title, value or path of a row"),
        ("Sessions", "⌘⏎ terminate ǀ ⌥⏎ device details ǀ ⏎ media actions"),
        ("Presets", "⏎ search ǀ ⌘⏎ edit ǀ ⌥⏎ delete ǀ ⌃⏎ duplicate ǀ ⇧⏎ move up"),
        ("Devices", "⏎ details ǀ ⌘⏎ remove"),
        ("Watchlist (account)", "⏎ find on your servers ǀ ⌘⏎ remove"),
    )
    items += [alfred.message(title, subtitle, icon_name="info") for title, subtitle in fixed]
    return items


# ----------------------------------------------------------- filters & sorts
@page("help/filters")
def sections(ctx: Context) -> list[Item]:
    saved = ctx.store.servers.items
    if not saved:
        return [alfred.message("No plex media server detected", "Press ⏎ and sign in to your plex account",
                               alfred.browse("accounts/new"))]

    def load(server: dict):
        plex = ctx.server(server["machineIdentifier"])
        return server, plex, plex.library.sections()

    items = []
    # v2 only kept the sections of the *last* server: every server is listed now.
    for result in parallel(load, saved):
        if isinstance(result, Exception):
            items.append(alfred.message(f"🚨 {result}"))
            continue
        server, plex, found = result
        for s in found:
            items.append(Item(
                s.title,
                fmt.join(plex.friendlyName, f"Scanner: {s.scanner}", f"Agent: {s.agent}"),
                intent=alfred.browse(nav.join("help", "filters", server["machineIdentifier"], s.key)),
                icon=alfred.icon(s.type),
            ))
    return items


def _unique(items: list[Item], item: Item, seen: set[str]) -> None:
    if item.title not in seen:
        seen.add(item.title)
        items.append(item)


@page("help/filters/<mid>/<key>")
def options(ctx: Context, mid: str, key: str) -> list[Item]:
    plex = ctx.server(mid)
    section = plex.library.sectionByID(int(key))
    alias = ctx.store.alias
    where = fmt.join(plex.friendlyName, section.title)
    items: list[Item] = []
    seen: set[str] = set()

    def target(kind: str, name: str, ftype: str, title: str):
        return alfred.browse(nav.join("help", "filters", mid, key, kind, name, ftype or "none", title))

    for filter_type in section.filterTypes():
        libtype = filter_type.type
        for f in section.listFilters(libtype=libtype):
            short = alias.short(f.filter)
            _unique(items, Item(f"Filter {f.title}", fmt.join(where, f"Name: {f.filter}", f"Alias: {short}"),
                                intent=target("filter", f.filter, f.filterType, f.title),
                                icon=alfred.icon("filter")), seen)
        for f in section.listFields(libtype=libtype):
            if "," not in f.key:
                _unique(items, Item(f"Field {f.title}", fmt.join(where, f"Name: {f.key}"),
                                    intent=target("field", f.key, f.type, f.title),
                                    icon=alfred.icon("field")), seen)
        for s in section.listSorts(libtype=libtype):
            if "," not in s.key:
                _unique(items, Item(f"Sort {s.title}", fmt.join(where, f"Name: {s.key}"),
                                    intent=target("sort", s.key, "none", s.title),
                                    icon=alfred.icon("sort")), seen)
    return items


@page("help/filters/<mid>/<key>/<kind>/<name>/<ftype>/<title>")
def choices(ctx: Context, mid: str, key: str, kind: str, name: str, ftype: str, title: str) -> list[Item]:
    plex = ctx.server(mid)
    section = plex.library.sectionByID(int(key))
    alias = ctx.store.alias
    libtypes = [t.type for t in section.filterTypes() if t.type != "folder"]
    items = [alfred.message("You can use alternative libtypes", f"Authorized libtypes: {', '.join(libtypes)}")]

    if kind == "filter":
        if ftype == "boolean":
            options = [("1", "is true"), ("0", "is false")]
        else:
            options = [(c.key, c.title) for c in section.listFilterChoices(name)]
        for value, label in options:
            query = to_text(alias, [("libtype", section.type), (name, unquote(str(value).replace("%25", "%")))])
            items.append(Item(label, f"Press ⏎ to apply the filter: {query}",
                              intent=alfred.search(query), icon=alfred.icon("filter")))
    elif kind == "field":
        for operator in section.listOperators(ftype):
            value = {"is true": 1, "is false": 0}.get(operator.title, "")
            advanced = {f"{name}{operator.key[:-1]}": value}
            query = to_text(alias, [("libtype", section.type), ("advancedFilters", advanced)])
            items.append(Item(f"{title} '{operator.title}'", f"Press ⏎ to apply the advanced filter: {query}",
                              intent=alfred.search(query), icon=alfred.icon("field")))
    elif kind == "sort":
        for label, direction in (("Ascending", "asc"), ("Descending", "desc")):
            query = to_text(alias, [("libtype", section.type), ("sort", f"{name}:{direction}")])
            items.append(Item(label, f"Press ⏎ to apply the sorting: {query}",
                              intent=alfred.search(query), icon=alfred.icon("sort")))
    return items


# --------------------------------------------------------------------- alias
@page("help/alias")
def alias(ctx: Context) -> list[Item]:
    here = alfred.browse("help/alias")
    items = [Item("Reset", "Reset the alias file to its default values",
                  intent=alfred.confirm("Reset the alias file?", "Your custom aliases will be lost",
                                        alfred.run("alias.reset", then=here)),
                  icon=alfred.icon("refresh"))]
    for entry in ctx.store.alias.entries:
        items.append(Item(
            entry.long,
            f"Alias: {entry.short} ǀ Press ⏎ to modify it",
            intent=alfred.ask(f"Modify alias of {entry.long}", f"Current alias: {entry.short}",
                              "alias.edit", then=here, long=entry.long),
            icon=alfred.icon("alias"),
            match=f"{entry.long} {entry.short}",
        ))
    return items


# --------------------------------------------------------------- cache/data
def _folder(ctx: Context, kind: str) -> list[Item]:
    folder = ctx.settings.cache_dir if kind == "cache" else ctx.settings.data_dir
    exists = folder.exists()
    pretty = str(folder).replace(str(folder.home()), "~", 1)
    here = alfred.browse(nav.join("help", kind))
    items = [
        Item(f"Display {kind.capitalize()} Folder", pretty if exists else f"{kind.capitalize()} folder doesn't exist",
             intent=alfred.reveal(str(folder)) if exists else None, icon=alfred.icon("finder")),
        Item(f"Clear {kind.capitalize()} Folder",
             "Delete cached objects and logs" if kind == "cache"
             else "Delete accounts, servers and alias (presets are kept)",
             intent=alfred.confirm(f"Clear the {kind} folder?", pretty,
                                   alfred.run("folder.clear", then=here, kind=kind)) if exists else None,
             icon=alfred.icon("delete")),
    ]
    if kind == "cache":
        count, size = posters.usage(ctx.settings)
        items.append(Item("🖼️ Posters & avatars", f"{fmt.plural(count, 'image')}, {fmt.size(size)} in the Alfred "
                                                     "cache ǀ ⏎ see them, purge all or one by one",
                             intent=alfred.browse("help/cache/posters"), icon=alfred.icon("photo")))
    log_file = ctx.settings.cache_dir / "plex.log"
    if kind == "cache" and log_file.exists():
        items += [
            Item("Export Workflow Logs", "Zip of the logs + versions in your downloads folder, for a GitHub issue",
                 intent=alfred.run("logs.export"), icon=alfred.icon("download")),
            Item("Show Log File", "Reveal plex.log in Finder",
                 intent=alfred.reveal(str(log_file)), icon=alfred.icon("document")),
        ]
    return items


@page("help/cache")
def cache(ctx: Context) -> list[Item]:
    return _folder(ctx, "cache")


@page("help/cache/posters")
def poster_cache(ctx: Context) -> list[Item]:
    """Every cached poster (type to find one): ⏎ removes it, ⌘⏎ shows it in Finder."""
    here = alfred.browse("help/cache/posters")
    found = posters.entries(ctx.settings)
    size = sum(path.stat().st_size for path, _ in found)
    folder = posters.folder(ctx.settings)
    items = [
        Item("🧹 Purge all posters", f"{fmt.plural(len(found), 'image')}, {fmt.size(size)} (posters and user "
                                     "avatars) ǀ they are downloaded again when needed",
             intent=alfred.confirm("Purge every poster?", f"{fmt.plural(len(found), 'image')}, {fmt.size(size)}",
                                   alfred.run("posters.purge", then=here)) if found else None,
             icon=alfred.icon("delete")),
        Item("Display Posters Folder", str(folder).replace(str(folder.home()), "~", 1),
             intent=alfred.reveal(str(folder)), icon=alfred.icon("finder")),
    ]
    now = time.time()
    for path, meta in found:
        label = meta.get("title") or path.stem
        days = int((now - path.stat().st_mtime) // 86400)
        cached = "today" if days == 0 else ("yesterday" if days == 1 else f"{days} days ago")
        items.append(Item(
            label,
            fmt.join(meta.get("kind"), meta.get("source"), fmt.size(path.stat().st_size), f"cached {cached}",
                     "⏎ remove from the cache ǀ ⌘⏎ show in Finder"),
            intent=alfred.run("posters.remove", then=here, name=path.name, title=label),
            icon=str(path),
            quicklook=str(path),
            match=fmt.join(label, meta.get("kind"), meta.get("source")),
            mods={"cmd": alfred.Mod("Show the file in Finder", alfred.reveal(str(path)), alfred.icon("finder"))},
        ))
    if not found:
        items.append(alfred.message("No poster in the cache", "Posters and avatars are downloaded when you show them",
                                    icon_name="photo"))
    return items


@page("help/data")
def data(ctx: Context) -> list[Item]:
    return _folder(ctx, "data")


@page("help/links")
def links(ctx: Context) -> list[Item]:
    items = []
    for title, url, img in LINKS:
        item = Item(title, url, intent=alfred.open_url(url), icon=alfred.icon(img, "web" if img != "web" else "base"))
        item.quicklook = url
        items.append(item)
    return items
