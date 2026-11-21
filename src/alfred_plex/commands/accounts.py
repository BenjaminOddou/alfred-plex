"""Account commands: sign in (OAuth, credentials, token), sync, remove."""

from __future__ import annotations

from typing import Any

from .. import alfred, nav, plex
from ..alfred import Intent
from ..context import Context
from ..system import failure, log, open_in_background, success, warning
from . import command, then

OAUTH_TIMEOUT = 180


def account_record(account: Any) -> dict:
    plex_pass = account.subscriptionDescription if account.subscriptionActive else "No"
    return {
        "title": account.friendlyName or account.username,
        "subtitle": f"Mail: {account.email} ǀ Plex Pass: {plex_pass}",
        "authToken": account.authToken,
        "uuid": account.uuid,
        "thumb": getattr(account, "thumb", None) or "",
    }


def server_record(account: Any, resource: Any, base_url: str) -> dict:
    return {
        "title": f"{resource.name} ({account.title})",
        "subtitle": f"Device: {resource.device} ǀ Version: {resource.platformVersion}",
        "friendlyName": resource.name,
        "machineIdentifier": resource.clientIdentifier,
        "baseURL": base_url,
        "plexToken": resource.accessToken,
        "account_uuid": account.uuid,
        "owner": resource.owned,
    }


def sync_servers(ctx: Context, account: Any) -> tuple[list[str], list[str]]:
    """Add / refresh every server of the account. Connections are tested in parallel."""
    resources = [r for r in account.resources() if "server" in (r.provides or "")]
    results = plex.parallel(lambda r: r.connect(timeout=plex.CONNECT_TIMEOUT), resources)
    added, failed = [], []
    for resource, result in zip(resources, results, strict=True):
        if isinstance(result, Exception):
            failed.append(resource.name)
            continue
        ctx.store.servers.upsert(server_record(account, resource, result._baseurl))
        added.append(resource.name)
    ctx.store.servers.save()
    return added, failed


def save_account(ctx: Context, account: Any) -> Intent | None:
    first = not ctx.store.accounts.items
    updated = ctx.store.accounts.upsert(account_record(account))
    ctx.store.accounts.save()
    plex.cache_account(ctx.settings, account)
    added, failed = sync_servers(ctx, account)
    verb = "updated" if updated else "added"
    message = f"{account.friendlyName or account.username} {verb}"
    message += f" ǀ Server(s): {', '.join(added)}" if added else " ǀ No server found"
    success(message)
    if failed:
        warning(f"Failed to connect to: {', '.join(failed)}")
    # a new user lands on the menu, which now shows his servers and what to do next
    return alfred.browse("") if first else alfred.browse(nav.join("accounts", account.uuid))


def _sign_in(ctx: Context, token: str) -> Intent | None:
    try:
        account = plex.sign_in(token)
    except Exception as error:  # noqa: BLE001
        failure("Failed to connect to your plex account", error)
        return then(ctx)
    return save_account(ctx, account)


@command("account.oauth")
def oauth(ctx: Context, text: str) -> Intent | None:
    """Sign in with Plex in the browser (MyPlexPinLogin OAuth, python-plexapi 4.18)."""
    from plexapi.myplex import MyPlexPinLogin

    login = MyPlexPinLogin(oauth=True)
    open_in_background(login.oauthUrl())
    hint = f"Complete the sign in in your browser ({OAUTH_TIMEOUT // 60} min max)"
    log.info(hint)  # the loading page says it too
    login.run(timeout=OAUTH_TIMEOUT)
    if not login.waitForLogin():
        warning("Plex sign in expired or was cancelled")
        return then(ctx)
    return _sign_in(ctx, token=login.token)


@command("account.sync")
def sync(ctx: Context, text: str) -> Intent | None:
    uuid = ctx.payload["uuid"]
    try:
        account = ctx.account(uuid, fresh=True)
    except Exception as error:  # noqa: BLE001
        failure("Failed to connect to your plex account, sign in again", error)
        return alfred.browse("accounts/new")
    save_account(ctx, account)
    return None


def remove_account(ctx: Context, uuid: str) -> str:
    removed = ctx.store.accounts.remove(uuid)
    ctx.store.servers.remove(uuid, field="account_uuid")
    ctx.store.accounts.save()
    ctx.store.servers.save()
    plex.forget_account(ctx.settings, uuid)
    return removed[0].get("title", uuid) if removed else uuid


@command("account.remove")
def remove(ctx: Context, text: str) -> None:
    name = remove_account(ctx, ctx.payload["uuid"])
    success(f"The account {name} and its servers are removed")


@command("device.remove")
def remove_device(ctx: Context, text: str) -> None:
    uuid, client_id = ctx.payload["uuid"], ctx.payload["client_id"]
    device = ctx.account(uuid).device(clientId=client_id)
    name = f"{device.name} - {device.platform} {device.platformVersion}"
    device.delete()
    success(f"The device '{name}' is removed")
    if ctx.payload.get("current"):
        remove_account(ctx, uuid)


@command("devices.cleanup")
def cleanup_devices(ctx: Context, text: str) -> None:
    """Remove the devices not seen for ``days`` (servers and this workflow are never removed)."""
    from ..views.accounts import stale_devices

    uuid = ctx.payload["uuid"]
    account = ctx.account(uuid)
    removed, failed = [], []
    for device in stale_devices(ctx, uuid, account.devices()):
        try:
            device.delete()
            removed.append(device.name)
        except Exception as error:  # noqa: BLE001 - keep cleaning the others
            log.warning("Cannot remove device %s: %r", device.name, error)
            failed.append(device.name)
    success(f"{len(removed)} old device(s) removed")
    if failed:
        warning(f"Failed to remove: {', '.join(failed)}")

