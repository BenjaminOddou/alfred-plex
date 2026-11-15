"""Yes / Cancel page shown before destructive commands (no more typing "yes")."""

from __future__ import annotations

import json

from .. import alfred
from ..alfred import Intent, Item
from ..context import Context
from . import menu_intent, page


@page("confirm")
def confirm(ctx: Context) -> list[Item]:
    try:
        data = json.loads(ctx.var("confirm") or "{}")
    except ValueError:
        data = {}
    yes = Intent.from_dict(data.get("yes"))
    cancel = alfred.pop(ctx.history) or menu_intent()
    return [
        alfred.message(data.get("title", "Are you sure?"), data.get("subtitle", ""), icon_name="info"),
        Item("Yes, continue", "This action cannot be undone", intent=yes, icon=alfred.icon("ok")),
        Item("No, cancel", "Back to where you were", intent=cancel, icon=alfred.icon("return")),
    ]
