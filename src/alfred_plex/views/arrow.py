"""→ on a media row, then ↩ on "Plex" in Alfred's actions panel: the action chosen in the configuration.

Alfred always shows its actions panel on → (Universal Actions): the workflow's action "Plex" comes first once
used. The row gives its path (``more/<mid>/<key>`` or ``more/discover/<uuid>/<kind>/<key>/<name>``) as text.
"""

from __future__ import annotations

from urllib.parse import quote

from .. import alfred, details, nav, posters
from ..alfred import Intent
from ..context import Context
from ..media import AUDIO, CLASSES, STREAMABLE, Source, stream_intent, web_url

LABELS = {
    "sheet": "📖 Full details",
    "more": "🔎 More details",
    "actions": "⚙️ Media actions page",
    "play": "▶️ Play",
    "web": "🌐 Open in Plex Web",
}


def label(ctx: Context) -> str:
    return LABELS[ctx.settings.right_arrow]


def intent_for(ctx: Context, path: str) -> Intent:
    """What the right arrow does on the media at ``path`` (falls back on the More details page)."""
    parts = nav.split(path)
    page = alfred.browse(path)
    try:
        if parts[1:2] == ["discover"] and len(parts) == 6:
            return _discover(ctx, page, *parts[2:]) or page
        if len(parts) == 3:
            return _library(ctx, page, parts[1], parts[2]) or page
    except Exception:  # noqa: BLE001 - the More details page shows the error
        from ..system import log

        log.exception("Right arrow on %s failed", path)
    return page


def _library(ctx: Context, page: Intent, mid: str, key: str) -> Intent | None:
    action = ctx.settings.right_arrow
    if action == "more":
        return page
    if action == "actions":
        return alfred.browse(nav.join("media", mid, key))
    plex = ctx.server(mid)
    media = plex.fetchItem(int(key))
    kind = CLASSES.get(type(media).__name__, (media.type, ""))[0]
    if action == "sheet":
        return alfred.details(str(details.prepare(ctx, plex, media, mid)))
    if action == "play":
        player = ctx.settings.media_player
        if kind in STREAMABLE and not (kind in AUDIO and player == "infuse"):
            return stream_intent(ctx, Source(ctx.store.server(mid) or {}, plex), media, kind)
        return None
    url = web_url(media, kind)
    return alfred.open_url(url) if url else None


def _discover(ctx: Context, page: Intent, uuid: str, kind: str, key: str, name: str) -> Intent | None:
    from .discover import WEB_URL
    from .more import discover_metadata

    action = ctx.settings.right_arrow
    if action == "web":
        folder = "people" if kind == "person" else "metadata"
        return alfred.open_url(WEB_URL.format(key=quote(f"/library/{folder}/{key}", safe="")))
    if action != "sheet" or kind == "person":
        return page  # no actions page nor player for Discover: the More details page
    account = ctx.account(uuid)
    element = discover_metadata(account, key)
    if element is None:
        return page
    a = element.attrib.get
    label_ = f"{a('title')} ({a('year')})" if a("title") and a("year") else (a("title") or name)
    thumb = posters.absolute(a("thumb"))
    poster = posters.url_posters(ctx.settings, account._session, {key: thumb},
                                 {key: {"title": label_, "kind": kind}}).get(key) if thumb else None
    text = details.discover_sheet(element, kind, label_, f"../posters/{poster.name}" if poster else None)
    return alfred.details(str(details.write(ctx.settings.cache_dir, f"discover-{key}", text)))
