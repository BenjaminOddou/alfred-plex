"""Prompt: a Script Filter instead of a Keyword input, so an input has a Return row too.

    ⏎ on the first row  → runs {var:cmd} with what you typed
    Return              → back to the screen you came from (nothing is changed)
"""

from __future__ import annotations

from .. import alfred
from ..alfred import Feedback, Intent, Item
from ..context import Context
from . import back_item


def render_prompt(ctx: Context) -> Feedback:
    title = ctx.var("prompt_title") or "Input"
    hint = ctx.var("prompt_subtitle")
    text = ctx.query
    action = Intent("run", arg=text, variables={
        key: ctx.var(key) for key in ("cmd", "payload", "run_id", "loading_label")
    })
    action.variables["nav"] = "loading"
    confirm = Item(
        f"{title}: {text}" if text else title,
        f"⏎ confirm ǀ {hint}" if text else f"Type, then ⏎ ǀ {hint}" if hint else "Type, then ⏎",
        intent=action,
        icon=alfred.icon("modify"),
        text=text or None,
    )
    feedback = Feedback([confirm, back_item(ctx)])
    alfred.link(feedback.items, None, ctx.history)  # a prompt never enters the history
    return feedback
