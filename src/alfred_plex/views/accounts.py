"""Plex Accounts pages."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .. import alfred, fmt, nav
from ..alfred import Intent, Item, Mod
from ..context import Context
from . import export_item, page

NEW_ACCOUNT = Item(
    "Connect a new plex account",
    "Sign in with Plex in your browser: the account and its servers are added",
    intent=alfred.run("account.oauth", then=alfred.browse("accounts")),
    icon=alfred.icon("add"),
)


def _account_item(account: dict, intent) -> Item:
    return Item(account.get("title", ""), account.get("subtitle", ""), intent=intent, icon=alfred.icon("person"))


@page("accounts")
def accounts(ctx: Context) -> list[Item]:
    saved = ctx.store.accounts.items
    items = [NEW_ACCOUNT]
    if saved:
        items.append(Item(
            "Remove the access to a plex account",
            "Remove a plex account and its connected plex media servers",
            intent=alfred.browse("accounts/remove"),
            icon=alfred.icon("delete"),
        ))
    items += [_account_item(a, alfred.browse(nav.join("accounts", a["uuid"]))) for a in saved]
    return items


def sign_in_item(then: Intent | None = None) -> Item:
    """The only way to connect: Plex OAuth in the browser (works with 2FA, Google, Apple...)."""
    return Item(
        "Sign in with Plex",
        "Opens app.plex.tv in your browser · works with 2FA, Google, Apple · nothing typed in Alfred",
        intent=alfred.run("account.oauth", then=then or alfred.browse("accounts")),
        icon=alfred.icon("add"),
    )


@page("accounts/new")
def connect(ctx: Context) -> list[Item]:
    return [
        sign_in_item(),
        alfred.message("How it works", "Sign in on the page that opens (3 min max): your servers are added "
                       "automatically and a notification tells you when it's done", icon_name="help"),
    ]


@page("accounts/remove")
def remove(ctx: Context) -> list[Item]:
    return [
        _account_item(a, alfred.confirm(
            f"Remove {a.get('title')}?",
            "The account and all its plex media servers will be removed from the workflow",
            alfred.run("account.remove", then=alfred.browse("accounts"), uuid=a["uuid"]),
        ))
        for a in ctx.store.accounts.items
    ]


@page("accounts/<uuid>")
def account(ctx: Context, uuid: str) -> list[Item]:
    here = nav.join("accounts", uuid)
    items = [Item(
        "Sync",
        "Refresh data from your plex account and reconnect your servers",
        intent=alfred.run("account.sync", then=alfred.browse(here), uuid=uuid),
        icon=alfred.icon("refresh"),
    )]
    for title, subtitle, sub, icon in (
        ("Servers", "Plex media servers connected to your account", "servers", "servers"),
        ("Users", "Plex users connected to your account", "users", "people"),
        ("Devices", "Manage connected devices to your account", "devices", "device"),
        ("Watchlist", "Manage your plex watchlist", "watchlist", "watchlist"),
    ):
        target = alfred.browse(nav.join("accounts", uuid, sub))
        items.append(Item(title, subtitle, intent=target, icon=alfred.icon(icon)))
    return items


@page("accounts/<uuid>/servers")
def servers(ctx: Context, uuid: str) -> list[Item]:
    plex_account = ctx.account(uuid)
    saved = {s.get("machineIdentifier") for s in ctx.store.servers.items}
    items = []
    for resource in plex_account.resources():
        if "server" not in (resource.provides or ""):
            continue
        added = resource.clientIdentifier in saved
        intent = (
            alfred.browse(nav.join("servers", resource.clientIdentifier))
            if added
            else alfred.run("account.sync", then=alfred.browse(nav.join("accounts", uuid, "servers")), uuid=uuid)
        )
        items.append(Item(
            f"{resource.name} ({plex_account.title})",
            fmt.join(f"Device: {resource.device}", f"Version: {resource.platformVersion}",
                     None if added else "Not added yet, press ⏎ to sync"),
            intent=intent,
            icon=alfred.icon("server" if added else "server_hide"),
        ))
    return items


@page("accounts/<uuid>/users")
def users(ctx: Context, uuid: str) -> list[Item]:
    found = ctx.account(uuid).users()
    items = [export_item("users", f"{fmt.plural(len(found), 'user')} to a CSV file", uuid=uuid)]
    for user in found:
        libraries = sum(s.numLibraries or 0 for s in user.servers)
        items.append(alfred.message(
            user.title,
            fmt.join(f"Email: {user.email}",
                     f"{user.title} has access to {fmt.plural(libraries, 'library', 'libraries')}"),
            icon_name="person",
        ))
    return items


def device_icon(ctx: Context, device) -> str:
    """Pick the icon whose name appears first in the device description."""
    folder: Path = ctx.settings.workflow_dir / "icons" / "devices"
    haystack = f"{device.name} {device.product} {device.platform} {device.platformVersion}".lower()
    best, best_index = "plex", len(haystack) + 1
    for file in folder.glob("*.webp"):
        index = haystack.find(file.stem)
        if file.stem != "plex" and 0 <= index < best_index:
            best, best_index = file.stem, index
    return alfred.icon(best, "devices")


def _is_current(ctx: Context, uuid: str, device) -> bool:
    saved = ctx.store.account(uuid) or {}
    return bool(device.token and device.token == saved.get("authToken"))


def stale_devices(ctx: Context, uuid: str, devices: list) -> list:
    """Devices not seen for ``stale_days`` (never servers, never this workflow)."""
    return [
        d for d in devices
        if fmt.days_since(d.lastSeenAt) >= ctx.settings.stale_days
        and "server" not in (d.provides or "") and not _is_current(ctx, uuid, d)
    ]


def _device_name(device) -> str:
    return f"{device.name} - {device.platform} {device.platformVersion}".strip(" -")


@page("accounts/<uuid>/devices")
def devices(ctx: Context, uuid: str) -> list[Item]:
    found = sorted(ctx.account(uuid).devices(), key=lambda d: d.lastSeenAt or datetime.min, reverse=True)
    here = alfred.browse(nav.join("accounts", uuid, "devices"))
    items = []
    stale = stale_devices(ctx, uuid, found)
    if stale:
        days = ctx.settings.stale_days
        items.append(Item(
            f"Clean up {fmt.plural(len(stale), 'old device')}",
            f"Remove the devices not seen for {days}+ days (servers and this workflow are kept)",
            intent=alfred.confirm(
                f"Remove {fmt.plural(len(stale), 'device')} not seen for {days}+ days?",
                ", ".join(_device_name(d) for d in stale[:8]) + ("…" if len(stale) > 8 else ""),
                alfred.run("devices.cleanup", then=here, uuid=uuid, days=days),
            ),
            icon=alfred.icon("delete"),
        ))
    items.append(export_item("devices", f"{fmt.plural(len(found), 'device')} to a CSV file", uuid=uuid))
    for device in found:
        current = " (current device)" if _is_current(ctx, uuid, device) else ""
        page_intent = alfred.browse(nav.join("accounts", uuid, "devices", device.clientIdentifier))
        items.append(Item(
            f"{_device_name(device)}{current}",
            fmt.join(f"Last seen {fmt.ago(device.lastSeenAt)}", device.product, device.device,
                     f"Created {fmt.day(device.createdAt, ctx.settings.date_format)}"),
            intent=page_intent,
            icon=device_icon(ctx, device),
            text=_device_name(device),
            mods={"cmd": Mod("Press ⏎ to remove this device", alfred.confirm(
                f"Remove {_device_name(device)}?", "The device will lose its access to your plex account",
                alfred.run("device.remove", then=alfred.browse("accounts") if current else here,
                           uuid=uuid, client_id=device.clientIdentifier, current=bool(current)),
            ), alfred.icon("delete"))},
        ))
    return items


@page("accounts/<uuid>/devices/<client_id>")
def device(ctx: Context, uuid: str, client_id: str) -> list[Item]:
    plex_account = ctx.account(uuid)
    dev = plex_account.device(clientId=client_id)
    name = _device_name(dev)
    current = _is_current(ctx, uuid, dev)
    after = alfred.browse("accounts") if current else alfred.browse(nav.join("accounts", uuid, "devices"))
    items = [
        Item(
            "Remove Device",
            "Revoke the access of the device to your plex account",
            intent=alfred.confirm(
                f"Remove {name}?",
                "This is the device used by this workflow: the account will be disconnected" if current
                else "The device will lose its access to your plex account",
                alfred.run("device.remove", then=after, uuid=uuid, client_id=client_id, current=current),
            ),
            icon=alfred.icon("delete"),
        ),
        alfred.message("Device", fmt.join(name, dev.product, dev.productVersion and f"v{dev.productVersion}",
                                          dev.model, dev.vendor), icon_name="device"),
        alfred.message("Activity", fmt.join(f"Last seen {fmt.ago(dev.lastSeenAt)}",
                                            f"Created {fmt.day(dev.createdAt, ctx.settings.date_format)}",
                                            dev.provides and f"Provides: {dev.provides}"), icon_name="history"),
    ]
    if dev.screenResolution:
        items.append(alfred.message("Screen", dev.screenResolution, icon_name="device"))
    if dev.publicAddress:
        geo = plex_account.geoip(dev.publicAddress)
        items += [
            alfred.message(
                "Device Location",
                fmt.join(f"IP: {dev.publicAddress}", f"City: {geo.city} ({geo.postalCode}), {geo.subdivisions}",
                         f"Country: {geo.country}", f"Timezone: {geo.timezone}"),
                icon_name="location",
            ),
            Item(
                "Google Maps",
                "Show the device location on Google Maps",
                intent=alfred.open_url(
                    "https://www.google.com/maps/search/?api=1&query=" + ",".join(map(str, geo.coordinates or ()))
                ),
                icon=alfred.icon("map"),
            ),
        ]
    return items


@page("accounts/<uuid>/watchlist")
def watchlist(ctx: Context, uuid: str) -> list[Item]:
    plex_account = ctx.account(uuid)
    here = alfred.browse(nav.join("accounts", uuid, "watchlist"))
    found = plex_account.watchlist()
    items = [
        Item("🖼️ Show as posters", "Your watchlist in Alfred's Grid View",
             intent=alfred.grid(nav.join("grid", "watchlist", uuid)), icon=alfred.icon("photo")),
        export_item("watchlist", f"{fmt.plural(len(found), 'media', 'medias')} to a CSV file", uuid=uuid),
    ]
    for media in found:
        label = f"{media.title}{fmt.year(media.year)}"
        detail = fmt.duration(media.duration) if media.type == "movie" else fmt.plural(
            getattr(media, "childCount", 0), "season")
        items.append(Item(
            label,
            fmt.join(media.type, detail, "⏎ find it on your servers"),
            intent=alfred.search(
                nav=nav.join("search", "guid", media.type, media.guid, label)
            ),
            icon=alfred.icon(f"{media.type}_discover_bookmarked"),
            mods={"cmd": Mod(
                f"Press ⏎ to remove the {media.type} from watchlist",
                alfred.run("watchlist", then=here, uuid=uuid, guid=media.guid, title=label, add=False),
                alfred.icon("delete"),
            )},
        ))
    return items
