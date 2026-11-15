"""Loading page: keeps Alfred open while a background command runs.

The Router opens this page *and* starts the command. The page polls the
command status (``rerun``) and, when it is over, becomes the page the user
came from with a ✅ / 🚨 banner on top (or a Return row when that page lives
in another Script Filter or in the Grid View).
"""

from __future__ import annotations

import time

from .. import alfred, runs
from ..alfred import Feedback, Intent, Item
from ..context import Context
from . import back_item, describe, page

ICONS = {"success": "ok", "warning": "info", "error": "delete"}


def banner(status: dict) -> Item:
    messages = status.get("messages") or []
    failed = status.get("state") == "error"
    if messages:
        level, text = messages[-1]
        title = f"{'🚨' if level == 'error' else '⚠️' if level == 'warning' else '✅'} {text}"
        others = " ǀ ".join(t for _, t in messages[:-1])
    else:
        title, others = ("🚨 The action failed, check the logs" if failed else "✅ Done"), ""
    item = alfred.message(title, others or "Done", icon_name="delete" if failed else "ok")
    item.text = " ǀ ".join(t for _, t in messages) or title
    return item


def running(ctx: Context, status: dict | None) -> Feedback:
    label = ctx.var("loading_label") or "Working"
    elapsed = int(time.time() - status["started"]) if status and status.get("started") else 0
    hint = "The result shows up here, you can also close Alfred: it keeps running"
    rows = [
        alfred.message(f"⏳ {label}…", f"{elapsed}s ǀ {hint}" if elapsed else hint, icon_name="refresh"),
        back_item(ctx),
    ]
    return Feedback(rows, rerun=0.5 if elapsed < 30 else 2)


def finished(ctx: Context, status: dict) -> Feedback:
    from . import render_browse

    origin = alfred.pop(ctx.history)
    next_step = Intent.from_dict(status.get("next"))
    extra = []
    if next_step is not None and next_step.action == "details":
        extra.append(Item("📖 Show the details again", "Opens the media sheet", intent=next_step,
                          icon=alfred.icon("info")))
    if origin is not None and origin.action == "browse":
        # Become the page the user came from, with the result on top.
        env = {**ctx.env, **origin.as_vars()}
        page_ctx = Context(settings=ctx.settings, store=ctx.store, env=env, nav=env.get("nav", ""))
        shown = render_browse(page_ctx)
        position = 1 if shown.items and shown.items[0].title == "Return" else 0
        shown.items[position:position] = [banner(status), *extra]
        return shown
    target = origin or alfred.browse("")
    target.variables.setdefault("back", "[]")
    back = Item("Return", f"Back to {describe(ctx, target)}", intent=target, icon=alfred.icon("return"))
    return Feedback([banner(status), *extra, back])


@page("loading")
def loading(ctx: Context) -> Feedback:
    status = runs.read(ctx.settings, ctx.var("run_id"))
    if status is None or status.get("state") == "running":
        return running(ctx, status)
    return finished(ctx, status)
