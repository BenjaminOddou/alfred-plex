"""Main menu (the ``plex`` keyword).

Subtitles show what is configured (read from local files only, so the menu
stays instant) and guide new users to the next step.
"""

from __future__ import annotations

from .. import alfred, fmt
from ..alfred import Item
from ..context import Context
from . import page


def _names(records: list[dict], key: str, limit: int = 3) -> str:
    names = [r.get(key) or r.get("title", "") for r in records]
    return ", ".join(names[:limit]) + ("…" if len(names) > limit else "")


@page("")
def menu(ctx: Context) -> list[Item]:
    accounts, servers = ctx.store.accounts.items, ctx.store.servers.items
    presets = ctx.store.presets.items
    items = []
    if not accounts:
        from .accounts import sign_in_item

        items += [
            sign_in_item(then=alfred.browse("")),
            Item("Getting started", "What this workflow can do, in 1 minute",
                 intent=alfred.browse("help/start"), icon=alfred.icon("help")),
        ]
    on_servers = f"on {fmt.plural(len(servers), 'server')}" if servers else "(add a server first)"
    items += [
        Item("Plex Search", f"Search medias {on_servers}, or browse your libraries (posters, sort, filters)",
             intent=alfred.search(), icon=alfred.icon("folder")),
        Item("Plex Discover", "Search movies, shows and people on Plex Discover",
             intent=alfred.discover(), icon=alfred.icon("discover")),
        Item("Plex Accounts", _names(accounts, "title") or "No account yet: sign in with Plex",
             intent=alfred.browse("accounts"), icon=alfred.icon("people")),
        Item("Plex Media Servers",
             f"{fmt.plural(len(servers), 'server')}: {_names(servers, 'friendlyName')}" if servers
             else "Sessions, libraries, statistics, settings, maintenance",
             intent=alfred.browse("servers"), icon=alfred.icon("servers")),
        Item("Plex Presets", f"{fmt.plural(len(presets), 'saved search', 'saved searches')} ǀ "
                             "Save a search from Plex Search to find it here",
             intent=alfred.browse("presets"), icon=alfred.icon("preset")),
        Item("Plex Help", "Getting started, shortcuts, filters & sorts, alias, cache, logs",
             intent=alfred.browse("help"), icon=alfred.icon("help")),
    ]
    return items
