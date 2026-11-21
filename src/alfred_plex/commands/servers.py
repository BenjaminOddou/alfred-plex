"""Server commands: backup, sessions, scan / refresh, settings, removal."""

from __future__ import annotations

from typing import Any

from .. import alfred
from ..alfred import Intent
from ..context import Context
from ..system import failure, success, warning
from . import command

SETTING_TYPES = {"bool", "int", "double", "text"}


def parse_setting(raw: str, kind: str) -> Any:
    """Convert what the user typed to the setting type (no more Python syntax needed).

    ``true`` / ``yes`` / ``1`` for booleans, plain text for strings
    (surrounding quotes are optional), numbers for int / double.
    """
    text = raw.strip()
    if kind == "bool":
        lowered = text.lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
        raise ValueError(f"'{raw}' is not a boolean (true / false)")
    if kind == "int":
        return int(text)
    if kind == "double":
        return float(text)
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    return text


@command("server.remove")
def remove(ctx: Context, text: str) -> None:
    removed = ctx.store.servers.remove(ctx.payload["mid"])
    ctx.store.servers.save()
    name = removed[0].get("title") if removed else "The server"
    success(f"The plex server {name} is removed")


@command("server.terminate")
def terminate(ctx: Context, text: str) -> None:
    plex = ctx.server(ctx.payload["mid"])
    key = int(ctx.payload["session"])
    session = next((s for s in plex.sessions() if s.sessionKey == key), None)
    if session is None:
        warning("This session is already over")
        return
    session.stop(reason=text.strip())
    success(f"The session '{ctx.payload.get('title', '')}' is terminated")


def _sections(ctx: Context):
    plex = ctx.server(ctx.payload["mid"])
    section = ctx.payload.get("section")
    target = plex.library.sectionByID(int(section)) if section not in (None, "") else plex.library
    name = target.title if section not in (None, "") else "all libraries"
    return plex, target, name


@command("server.scan")
def scan(ctx: Context, text: str) -> None:
    plex, target, name = _sections(ctx)
    target.update()
    success(f"Scan started for {name} on {plex.friendlyName}")


@command("server.refresh")
def refresh(ctx: Context, text: str) -> None:
    plex, target, name = _sections(ctx)
    target.refresh()
    success(f"Refresh started for {name} on {plex.friendlyName}")


@command("server.setting")
def setting(ctx: Context, text: str) -> None:
    plex = ctx.server(ctx.payload["mid"])
    item = plex.settings.get(ctx.payload["id"])
    try:
        value = parse_setting(text, item.type)
    except ValueError as error:
        failure(f"Invalid value for {item.id} ({item.type}): {error}")
        return
    item.set(value)
    plex.settings.save()
    success(f"{item.id} value is now {value}")


@command("server.terminate_all")
def terminate_all(ctx: Context, text: str) -> None:
    plex = ctx.server(ctx.payload["mid"])
    stopped = 0
    for session in plex.sessions():
        if session.session is not None:
            session.stop(reason=text.strip())
            stopped += 1
    success(f"{stopped} session(s) terminated on {plex.friendlyName}")


@command("server.logs")
def logs(ctx: Context, text: str) -> Intent:
    plex = ctx.server(ctx.payload["mid"])
    path = plex.downloadLogs(savepath=str(ctx.settings.downloads_dir))
    success(f"{plex.friendlyName} logs saved in {ctx.settings.downloads_dir}")
    return alfred.reveal(str(path))


@command("server.databases")
def databases(ctx: Context, text: str) -> Intent:
    plex = ctx.server(ctx.payload["mid"])
    path = plex.downloadDatabases(savepath=str(ctx.settings.downloads_dir))
    success(f"{plex.friendlyName} databases saved in {ctx.settings.downloads_dir}")
    return alfred.reveal(str(path))


@command("server.analyze")
def analyze(ctx: Context, text: str) -> None:
    plex, target, name = _sections(ctx)
    target.analyze()
    success(f"Analysis started for {name} on {plex.friendlyName}")


@command("server.trash")
def empty_trash(ctx: Context, text: str) -> None:
    plex, target, name = _sections(ctx)
    target.emptyTrash()
    success(f"Trash emptied for {name} on {plex.friendlyName}")


@command("server.bundles")
def clean_bundles(ctx: Context, text: str) -> None:
    plex = ctx.server(ctx.payload["mid"])
    plex.library.cleanBundles()
    success(f"Bundles cleaning started on {plex.friendlyName}")


@command("server.optimize")
def optimize(ctx: Context, text: str) -> None:
    plex = ctx.server(ctx.payload["mid"])
    plex.library.optimize()
    success(f"Database optimization started on {plex.friendlyName}")


@command("server.butler")
def butler(ctx: Context, text: str) -> None:
    plex = ctx.server(ctx.payload["mid"])
    plex.runButlerTask(ctx.payload["task"])
    success(f"Task '{ctx.payload.get('title', ctx.payload['task'])}' started on {plex.friendlyName}")


@command("server.install")
def install_update(ctx: Context, text: str) -> None:
    plex = ctx.server(ctx.payload["mid"])
    if not plex.canInstallUpdate():
        warning(f"{plex.friendlyName} can't install updates by itself: download it instead")
        return
    plex.installUpdate()
    success(f"{plex.friendlyName} is installing the update")
