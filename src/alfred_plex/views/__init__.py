"""Script Filter pages.

* ``browse``   → menu, accounts, servers, presets, help (Alfred filters the rows)
* ``search``   → live search on the saved servers
* ``discover`` → live search on Plex Discover
"""

from __future__ import annotations

import json

from .. import alfred, nav
from ..alfred import Feedback, Intent, Item
from ..context import Context
from ..plex import PlexError

router = nav.Router()
page = router.page

LABELS = {
    "accounts": "Plex Accounts",
    "servers": "Plex Media Servers",
    "presets": "Plex Presets",
    "help": "Plex Help",
    "new": "Connect",
    "remove": "Remove",
    "users": "Users",
    "devices": "Devices",
    "watchlist": "Watchlist",
    "sessions": "Sessions",
    "settings": "Settings",
    "stats": "Statistics",
    "libraries": "Library Sections",
    "history": "History",
    "filters": "Filters & Sorts",
    "alias": "Alias",
    "cache": "Cache",
    "data": "Data",
    "links": "Links",
    "maintenance": "Maintenance",
    "activities": "Activities",
    "recent": "Recently Added",
    "continue": "Continue Watching",
    "live": "Live",
    "plays": "Plays",
    "bandwidth": "Bandwidth",
    "quality": "Media Quality",
    "start": "Getting Started",
    "shortcuts": "Shortcuts",
    "library": "Plex Libraries",
    "more": "More details",
    "posters": "Posters",
}


def label(ctx: Context, segment: str) -> str | None:
    """Human name of a path segment, None for technical ones (ids, keys...)."""
    if segment in LABELS:
        return LABELS[segment]
    for record, key in ((ctx.store.server(segment), "friendlyName"), (ctx.store.account(segment), "title"),
                        (ctx.store.presets.get(segment), "title")):
        if record:
            return record.get(key) or record.get("title") or segment
    return None


def breadcrumb(ctx: Context, path: str) -> str:
    names = [label(ctx, p) for p in nav.split(path)]
    return " › ".join(["Menu"] + [n for n in names if n])


TRANSIENT = {"confirm", "loading"}  # pages that never enter the history


def menu_intent() -> Intent:
    intent = alfred.browse("")
    intent.variables["back"] = "[]"  # fresh start: no history
    return intent


def return_item(ctx: Context, target: Intent, where: str) -> Item:
    if "back" not in target.variables:
        target.variables["back"] = "[]"
    item = Item("Return", f"Back to {where}  ·  ⌘⏎ main menu", intent=target, icon=alfred.icon("return"))
    item.mods["cmd"] = alfred.Mod("Back to the main menu", menu_intent(), alfred.icon("return"))
    return item


def describe(ctx: Context, intent: Intent) -> str:
    """Where a Return goes, in words."""
    if intent.action == "browse":
        return breadcrumb(ctx, intent.variables.get("nav", ""))
    if intent.action == "search":
        return f"Plex Search '{intent.arg}'" if intent.arg else "Plex Search"
    if intent.action == "discover":
        return f"Plex Discover '{intent.arg}'" if intent.arg else "Plex Discover"
    if intent.action == "grid":
        return "the posters"
    return "the previous page"


def parent_intent(path: str) -> Intent:
    """Closest ancestor that is a real page (used when there is no history)."""
    parent = nav.parent(path)
    while parent and router.resolve(parent) is None:
        parent = nav.parent(parent)
    return alfred.browse(parent)


def back_item(ctx: Context, default: Intent | None = None) -> Item:
    """Return row: the screen the user came from, or ``default`` (menu) without history."""
    target = alfred.pop(ctx.history) or default or menu_intent()
    return return_item(ctx, target, describe(ctx, target))


def back_to_parent(ctx: Context, path: str) -> Item:
    return back_item(ctx, parent_intent(path))


def export_item(kind: str, what: str, title: str = "Export to CSV", **params: object) -> Item:
    """Row that writes a CSV file in the downloads folder, then shows it in Finder."""
    return Item(title, f"Save {what} in your 📁 Downloads folder",
                intent=alfred.run("export", kind=kind, **params), icon=alfred.icon("download"))


def error_item(error: Exception) -> Item:
    text = str(error) if isinstance(error, PlexError) else "Something went wrong, check the logs"
    return alfred.message(f"🚨 {text}", "See plex.log in Plex Help › Workflow Cache")


LAST_PAGE = "last_page.json"


def remember_page(ctx: Context, here: Intent | None, items: list[Item] | None = None) -> None:
    """Keep the page on screen and the → targets of its rows.

    → on a row opens Alfred's actions panel with the row's text (its title): the "Plex" action finds the media
    back from that text, and Return comes back to this page. Universal Actions don't carry the workflow
    variables, so both are kept in the cache.
    """
    if here is None:
        return
    arrows = {item.action: item.arrow for item in items or [] if item.action and item.arrow}
    try:
        ctx.settings.cache_dir.mkdir(parents=True, exist_ok=True)
        (ctx.settings.cache_dir / LAST_PAGE).write_text(
            json.dumps({"page": here.page(), "history": ctx.history, "arrows": arrows}, ensure_ascii=False),
            encoding="utf-8")
    except OSError:  # best effort
        pass


def _last(ctx: Context) -> dict:
    try:
        data = json.loads((ctx.settings.cache_dir / LAST_PAGE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def last_page(ctx: Context) -> list[dict]:
    """History stack ending with the last page shown by the workflow (see :func:`remember_page`)."""
    data = _last(ctx)
    try:
        return alfred.parse_history(json.dumps([*data.get("history", []), data["page"]]))
    except (KeyError, TypeError):
        return []


def last_arrows(ctx: Context) -> dict[str, str]:
    """{row text: → target} of the last page shown."""
    arrows = _last(ctx).get("arrows")
    return arrows if isinstance(arrows, dict) else {}


def render_browse(ctx: Context) -> Feedback:
    # Importing the sections registers their pages on the router.
    from . import accounts, confirm, library, loading, media_page, menu, more, presets, servers, stats  # noqa: F401
    from . import help as _help  # noqa: F401

    path = ctx.nav
    resolved = router.resolve(path)
    if resolved is None:  # unknown or outdated path: fall back to the menu
        path, resolved = "", router.resolve("")
    handler, params = resolved
    feedback = Feedback()
    if path and path not in TRANSIENT:
        feedback.add(back_to_parent(ctx, path))
    try:
        result = handler(ctx, **params)
    except Exception as error:  # noqa: BLE001 - always answer Alfred with something
        from ..system import log

        log.exception("Page %s failed", path)
        result = [error_item(error)]
    if isinstance(result, Feedback):
        feedback.extend(result.items)
        feedback.rerun = result.rerun
    else:
        feedback.extend(result or [])
    here = None if path in TRANSIENT else alfred.browse(path, state=ctx.state or None)
    alfred.link(feedback.items, here, ctx.history)
    if any(item.arrow for item in feedback.items):
        remember_page(ctx, here, feedback.items)
    return feedback
