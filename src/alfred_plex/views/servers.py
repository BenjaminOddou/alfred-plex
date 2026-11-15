"""Plex Media Servers pages."""

from __future__ import annotations

from .. import alfred, fmt, nav, stats
from ..alfred import Feedback, Item, Mod
from ..context import Context
from ..media import Source, prefetch_posters, to_item
from . import export_item, page

SECTION_SUBTYPES = {"show": ("season", "episode"), "artist": ("album", "track")}
HISTORY_MAX = 200


def _server_item(server: dict, intent) -> Item:
    return Item(server.get("title", ""), server.get("subtitle", ""), intent=intent, icon=alfred.icon("server"))


@page("servers")
def servers(ctx: Context) -> list[Item]:
    saved = ctx.store.servers.items
    if not saved:
        return [alfred.message("No plex media server detected", "Press ⏎ and sign in to your plex account",
                               alfred.browse("accounts/new"))]
    items = [Item(
        "Remove the access to a server",
        "Remove the access of this workflow to the plex media server",
        intent=alfred.browse("servers/remove"),
        icon=alfred.icon("delete"),
    )]
    items += [_server_item(s, alfred.browse(nav.join("servers", s["machineIdentifier"]))) for s in saved]
    return items


@page("servers/remove")
def remove(ctx: Context) -> list[Item]:
    return [
        _server_item(s, alfred.confirm(
            f"Remove {s.get('title')}?",
            "The workflow will forget this server (sync the account to add it again)",
            alfred.run("server.remove", then=alfred.browse("servers"), mid=s["machineIdentifier"]),
        ))
        for s in ctx.store.servers.items
    ]


@page("servers/<mid>")
def server(ctx: Context, mid: str) -> list[Item]:
    saved = ctx.store.server(mid) or {}
    owner = bool(saved.get("owner"))
    account = ctx.store.account(saved.get("account_uuid", ""))
    plex = ctx.server(mid)
    items = []
    if owner:
        # One cached check (v2 forced two update checks against plex.tv on every visit).
        release = plex.checkForUpdate(force=False, download=False)
        if release:
            items.append(Item(
                "Update to the latest version",
                f"Actual version: {plex.version} -> New version: {release.version} ǀ ⌘⏎ install it now",
                intent=alfred.open_url(release.downloadURL),
                icon=alfred.icon("update"),
                mods={"cmd": Mod("Press ⏎ to let the server install the update (Mac / Windows servers)",
                                 alfred.confirm(f"Install Plex Media Server {release.version}?",
                                                "The server restarts: running sessions stop",
                                                alfred.run("server.install", mid=mid)), alfred.icon("update"))},
            ))
        else:
            items.append(alfred.message("Your server is up to date",
                                        fmt.join(f"Version {plex.version}", plex.platform), icon_name="ok"))
        playing = len(plex.sessions())
        items.append(Item("Sessions", f"{fmt.plural(playing, 'stream')} playing ǀ terminate, see devices",
                          intent=alfred.browse(nav.join("servers", mid, "sessions")), icon=alfred.icon("watch")))
    else:
        items.append(alfred.message("Shared server", "You are not the owner: server management is not available"))
    pages = [
        ("Recently Added", "The last medias added to this server", "recent", "update"),
        ("Continue Watching", "Resume what you started", "continue", "watch"),
    ]
    if owner:
        pages += [
            ("Library Sections", "Scan, refresh, analyze, empty trash, history, export", "libraries", "library"),
            ("Statistics", "Live usage, libraries, plays, bandwidth, media quality", "stats", "statistics"),
            ("Settings", "Modify your plex media server settings", "settings", "setting"),
            ("Maintenance", "Logs, databases, trash, bundles, optimization, scheduled tasks", "maintenance", "data"),
            ("Activities", "What the server is doing right now (scans, analysis...)", "activities", "refresh"),
        ]
    for title, subtitle, sub, icon in pages:
        items.append(Item(title, subtitle, intent=alfred.browse(nav.join("servers", mid, sub)), icon=alfred.icon(icon)))
    if account:
        from .accounts import account_avatars

        avatar = account_avatars(ctx, [account]).get(account["uuid"])
        items.append(Item(account.get("title", ""), account.get("subtitle", ""),
                          intent=alfred.browse(nav.join("accounts", account["uuid"])),
                          icon=avatar or alfred.icon("person")))
    return items


# ------------------------------------------------------------ media lists
def media_rows(ctx: Context, mid: str, medias, here) -> list[Item]:
    src = Source(ctx.store.server(mid) or {}, ctx.server(mid))
    watchlist = ctx.watchlist(src.account_uuid) if src.account_uuid else set()
    prefetch_posters(ctx, [(src, media) for media in medias])
    rows = [to_item(ctx, src, media, watchlist, here) for media in medias]
    return [row for row in rows if row] or [alfred.message("Nothing here yet", icon_name="info")]


def posters_item(target, what: str) -> Item:
    return Item("🖼️ Show as posters", f"{what} in Alfred's Grid View", intent=target, icon=alfred.icon("photo"))


@page("servers/<mid>/recent")
def recent(ctx: Context, mid: str) -> list[Item]:
    here = alfred.browse(nav.join("servers", mid, "recent"))
    medias = ctx.server(mid).library.recentlyAdded()[: ctx.settings.limit * 2]
    return [posters_item(alfred.grid(nav.join("grid", "recent", mid)), "The last medias added"),
            *media_rows(ctx, mid, medias, here)]


@page("servers/<mid>/continue")
def continue_watching(ctx: Context, mid: str) -> list[Item]:
    here = alfred.browse(nav.join("servers", mid, "continue"))
    medias = ctx.server(mid).continueWatching()
    return [posters_item(alfred.grid(nav.join("grid", "continue", mid)), "What you started"),
            *media_rows(ctx, mid, medias, here)]


# ---------------------------------------------------------------- sessions
def session_title(session) -> str:
    if session.type == "movie":
        return f"{session.title}{fmt.year(session.year)}"
    if session.type == "episode":
        return fmt.join(session.grandparentTitle, session.title, session.seasonEpisode)
    return session.title


def session_quality(session) -> str:
    transcode = session.transcodeSession
    if transcode is None:
        mode = "Direct Play"
    else:
        mode = f"Transcode (video {transcode.videoDecision or '-'}, audio {transcode.audioDecision or '-'})"
    link = session.session
    return fmt.join(mode, link and link.bandwidth and f"{link.bandwidth} kbps", link and link.location)


def session_avatars(ctx: Context, found) -> dict[str, str]:
    """{user name: avatar path} of the users watching (cached: the page refreshes every 5 seconds)."""
    from .. import posters

    wanted = {}
    for session in found:
        user = session._data.find("User") if getattr(session, "_data", None) is not None else None
        name = getattr(session, "_username", None)
        if user is not None and name and user.attrib.get("thumb", "").startswith("http"):
            wanted[name] = (name, user.attrib["thumb"])
    if not wanted:
        return {}
    try:
        return {k: str(v) for k, v in posters.avatars(ctx.settings, posters.web_session(), wanted).items()}
    except Exception:  # noqa: BLE001 - an avatar is a nice-to-have
        return {}


@page("servers/<mid>/sessions")
def sessions(ctx: Context, mid: str) -> Feedback:
    saved = ctx.store.server(mid) or {}
    uuid = saved.get("account_uuid", "")
    found = ctx.server(mid).sessions()
    items = []
    if len(found) > 1:
        items.append(Item(
            f"Terminate all {len(found)} sessions", "Type a message displayed on every player",
            intent=alfred.ask("Terminate all sessions", "Message displayed on the players", "server.terminate_all",
                              mid=mid),
            icon=alfred.icon("delete"),
        ))
    avatars = session_avatars(ctx, found)
    for session in found:
        name = session_title(session)
        player = session.player
        where = f"{player.product} - {player.device} {player.platform}" if player else None
        progress = f"{fmt.duration(session.viewOffset)} / {fmt.duration(session.duration)}" if session.duration \
            else fmt.duration(session.viewOffset)
        item = Item(
            name,
            fmt.join(", ".join(session.usernames), where, f"{progress} {player.state if player else ''}".strip(),
                     session_quality(session)),
            icon=avatars.get(getattr(session, "_username", None) or "", alfred.icon("watch")),
            text=name,
            mods={
                "cmd": Mod(
                    "Press ⏎ to terminate this session",
                    alfred.ask(f"Terminate {name}", "Type the message you want to display on the player",
                               "server.terminate", mid=mid, session=session.sessionKey, title=name),
                    alfred.icon("delete"),
                ),
            },
        )
        if session.ratingKey:
            item.intent = alfred.browse(nav.join("media", mid, session.ratingKey))
        if uuid and player and player.machineIdentifier:
            item.mods["alt"] = Mod("Press ⏎ to see the device details",
                                   alfred.browse(nav.join("accounts", uuid, "devices", player.machineIdentifier)),
                                   alfred.icon("device"))
        items.append(item)
    if not found:
        items.append(alfred.message("No running session", "Nothing is playing on this server right now",
                                    icon_name="watch"))
    else:
        items.append(export_item("sessions", "the running sessions to a CSV file", mid=mid))
    return Feedback(items, rerun=5)


# ------------------------------------------------------------- maintenance
@page("servers/<mid>/maintenance")
def maintenance(ctx: Context, mid: str) -> list[Item]:
    plex = ctx.server(mid)
    here = alfred.browse(nav.join("servers", mid, "maintenance"))
    folder = ctx.settings.downloads_dir

    def confirmed(title: str, subtitle: str, cmd: str, icon: str) -> Item:
        return Item(title, subtitle, intent=alfred.confirm(f"{title}?", subtitle, alfred.run(cmd, mid=mid)),
                    icon=alfred.icon(icon))

    items = [
        Item("Download server logs", f"Zip of the Plex Media Server logs in {folder}",
             intent=alfred.run("server.logs", mid=mid), icon=alfred.icon("download")),
        Item("Download databases", f"Backup of the Plex Media Server databases in {folder}",
             intent=alfred.run("server.databases", mid=mid), icon=alfred.icon("download")),
        confirmed("Empty trash", "Delete the medias marked as deleted in every library section",
                  "server.trash", "delete"),
        confirmed("Clean bundles", "Remove unused metadata bundles to free disk space", "server.bundles", "data"),
        confirmed("Optimize database", "Compact the server database (the server can be slower meanwhile)",
                  "server.optimize", "update"),
    ]
    for task in plex.butlerTasks():
        items.append(Item(
            f"Run task: {task.title or task.name}",
            fmt.join(task.description, f"every {fmt.plural(task.interval, 'day')}" if task.interval else None,
                     "enabled" if task.enabled else "disabled"),
            intent=alfred.run("server.butler", then=here, mid=mid, task=task.name, title=task.title or task.name),
            icon=alfred.icon("refresh"),
        ))
    return items


@page("servers/<mid>/activities")
def activities(ctx: Context, mid: str) -> Feedback:
    found = ctx.server(mid).activities
    items = [
        alfred.message(a.title or a.type, fmt.join(a.subtitle, a.progress is not None
                                                    and f"{fmt.bar(a.progress, 100)} {a.progress}%"),
                       icon_name="refresh")
        for a in found
    ]
    return Feedback(items or [alfred.message("The server is idle", "No scan, analysis or download running",
                                             icon_name="ok")], rerun=2)


# ---------------------------------------------------------------- settings
@page("servers/<mid>/settings")
def settings_groups(ctx: Context, mid: str) -> list[Item]:
    items = [export_item("settings", "every setting (value, default, type) to a CSV file", mid=mid)]
    for group, settings in ctx.server(mid).settings.groups().items():
        if not group:
            continue
        visible = sum(1 for s in settings if not s.hidden)
        items.append(Item(
            group.capitalize(),
            f"Display {group.capitalize()} settings ǀ {fmt.plural(visible, 'element')}",
            intent=alfred.browse(nav.join("servers", mid, "settings", group)),
            icon=alfred.icon("setting"),
        ))
    return items


@page("servers/<mid>/settings/<group>")
def settings_group(ctx: Context, mid: str, group: str) -> list[Item]:
    here = alfred.browse(nav.join("servers", mid, "settings", group))
    items = []
    for setting in ctx.server(mid).settings.group(group):
        if setting.hidden:
            continue
        info = "\n".join(f"{name}: {value}" for name, value in (
            ("ID", setting.id), ("Value", setting.value), ("Type", setting.type),
            ("Default", setting.default), ("Summary", setting.summary)))
        items.append(Item(
            setting.label,
            fmt.join(f"{setting.id}: {setting.value}", f"Type: {setting.type}", f"Default: {setting.default}",
                     setting.summary),
            intent=alfred.ask(
                f"Configure {setting.label}",
                f"New value ({setting.type}) ǀ Current: {setting.value} ǀ Default: {setting.default}",
                "server.setting", then=here, mid=mid, id=setting.id,
            ),
            icon=alfred.icon("setting"),
            text=info,
        ))
    return items


# --------------------------------------------------------------- libraries
@page("servers/<mid>/libraries")
def libraries(ctx: Context, mid: str) -> list[Item]:
    plex = ctx.server(mid)
    sections = plex.library.sections()
    scanning = any(s.refreshing for s in sections)
    updated = max((s.updatedAt for s in sections if s.updatedAt), default=None)
    items = [
        Item("Scan All Library Sections", f"Scan all sections for new media ǀ Scanning: {scanning}",
             intent=alfred.run("server.scan", mid=mid), icon=alfred.icon("scan")),
        Item("Refresh All Library Sections",
             "Forces a download of fresh media infos from the internet ǀ "
             f"Last refresh: {fmt.day(updated, ctx.settings.date_format)}",
             intent=alfred.run("server.refresh", mid=mid), icon=alfred.icon("refresh")),
        Item("Library Sections History", f"History of the last {ctx.settings.history_days} days for all sections",
             intent=alfred.browse(nav.join("servers", mid, "libraries", "history")), icon=alfred.icon("history")),
    ]
    for s in sections:
        items.append(Item(
            s.title,
            fmt.join(plex.friendlyName, f"Scanner: {s.scanner}", f"Agent: {s.agent}"),
            intent=alfred.browse(nav.join("servers", mid, "libraries", s.key)),
            icon=alfred.icon(s.type),
        ))
    return items


@page("servers/<mid>/libraries/<key>")
def library(ctx: Context, mid: str, key: str) -> list[Item]:
    plex = ctx.server(mid)
    section = plex.library.sectionByID(int(key))
    sizes = [fmt.plural(section.totalViewSize(libtype=section.type, includeCollections=False), section.type)]
    sizes += [fmt.plural(section.totalViewSize(libtype=t, includeCollections=False), t)
              for t in SECTION_SUBTYPES.get(section.type, ())]
    alias = ctx.store.alias
    duration, size = stats.storage_map(plex).get(section.key, (0, 0))
    return [
        alfred.message(f"{section.title}: {', '.join(sizes)}",
                       fmt.join(fmt.size(size), fmt.hours(duration),
                                f"Scanner: {section.scanner}", f"Agent: {section.agent}"), icon_name=section.type),
        Item(f"📚 Browse {section.title}", "Sort and filter by picking in lists, as a list or as posters",
             intent=alfred.browse(nav.join("library", mid, key)), icon=alfred.icon("library"),
             mods={"cmd": Mod("Show it as posters", alfred.grid(nav.join("grid", "library", mid, key),
                                                                state={"view": "grid"}), alfred.icon("photo"))}),
        Item("Recently Added", f"The last medias added to {section.title}",
             intent=alfred.browse(nav.join("servers", mid, "libraries", key, "recent")), icon=alfred.icon("update")),
        Item(f"Search in {section.title}", "Open Plex Search on this section only",
             intent=alfred.search(f"{alias.display('section')}={section.title}/{alias.display('title')}="),
             icon=alfred.icon("folder")),
        Item(f"Scan {section.title}", f"Look for new files ǀ Scanning: {section.refreshing}",
             intent=alfred.run("server.scan", mid=mid, section=section.key), icon=alfred.icon("scan")),
        Item(f"Refresh {section.title}",
             "Forces a download of fresh media infos from the internet ǀ "
             f"Last refresh: {fmt.day(section.updatedAt, ctx.settings.date_format)}",
             intent=alfred.run("server.refresh", mid=mid, section=section.key), icon=alfred.icon("refresh")),
        Item(f"Analyze {section.title}", "Analyze every media of the section (codecs, loudness...)",
             intent=alfred.run("server.analyze", mid=mid, section=section.key), icon=alfred.icon("scan")),
        Item(f"Empty {section.title} trash", "Delete the medias marked as unavailable",
             intent=alfred.confirm(f"Empty the trash of {section.title}?", "Unavailable medias are removed",
                                   alfred.run("server.trash", mid=mid, section=section.key)),
             icon=alfred.icon("delete")),
        Item(f"{section.title} History", f"History of the last {ctx.settings.history_days} days for this section",
             intent=alfred.browse(nav.join("servers", mid, "libraries", key, "history")),
             icon=alfred.icon("history")),
        export_item("library", f"every {section.type} of {section.title} (title, year, file, size, quality...) "
                    "to a CSV file", mid=mid, section=section.key),
    ]


@page("servers/<mid>/libraries/<key>/recent")
def library_recent(ctx: Context, mid: str, key: str) -> list[Item]:
    section = ctx.server(mid).library.sectionByID(int(key))
    medias = section.recentlyAdded(maxresults=ctx.settings.limit * 2)
    return media_rows(ctx, mid, medias, alfred.browse(nav.join("servers", mid, "libraries", key, "recent")))


def history_items(ctx: Context, mid: str, entries) -> list[Item]:
    plex = ctx.server(mid)
    sections = {s.key: s.title for s in plex.library.sections()}
    accounts = {a.id: a.name for a in plex.systemAccounts()}
    devices = {d.id: f"{d.name}, {d.platform}" for d in plex.systemDevices()}
    items = []
    for entry in entries:
        if entry.type == "movie":
            name = f"{entry.title}{fmt.year(entry.year)}"
        elif entry.type == "episode":
            name = fmt.join(entry.grandparentTitle, entry.title, entry.seasonEpisode)
        elif entry.type == "track":
            name = fmt.join(entry.grandparentTitle, entry.title)
        else:
            name = entry.title
        items.append(alfred.message(
            name,
            fmt.join(plex.friendlyName, sections.get(entry.librarySectionID, "Deleted Library"), entry.type,
                     fmt.day(entry.viewedAt, ctx.settings.date_format), accounts.get(entry.accountID),
                     devices.get(entry.deviceID)),
            icon_name="history",
        ))
    return items or [alfred.message("No history", f"Nothing played during the last {ctx.settings.history_days} days")]


@page("servers/<mid>/libraries/history")
def history_all(ctx: Context, mid: str) -> list[Item]:
    entries = ctx.server(mid).history(maxresults=HISTORY_MAX, mindate=fmt.since(ctx.settings.history_days))
    return [export_item("history", f"the last {ctx.settings.history_days} days of history to a CSV file", mid=mid),
            *history_items(ctx, mid, entries)]


@page("servers/<mid>/libraries/<key>/history")
def history_section(ctx: Context, mid: str, key: str) -> list[Item]:
    section = ctx.server(mid).library.sectionByID(int(key))
    entries = section.history(maxresults=HISTORY_MAX, mindate=fmt.since(ctx.settings.history_days))
    return [export_item("history", f"the history of {section.title} to a CSV file", mid=mid, section=section.key),
            *history_items(ctx, mid, entries)]
