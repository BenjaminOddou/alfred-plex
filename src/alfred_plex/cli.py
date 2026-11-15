"""Command line dispatcher used by every object of the Alfred diagram.

    python3 main.py browse   [query]   # Script Filter "Plex" (menu, accounts, servers, presets, help)
    python3 main.py search   [query]   # Script Filter "Plex Search"
    python3 main.py discover [query]   # Script Filter "Plex Discover"
    python3 main.py grid               # Grid View: posters ({var:nav})
    python3 main.py prompt   [text]    # Script Filter "Plex Prompt": text input with a Return row
    python3 main.py run      [input]   # Run Script: executes {var:cmd} with {var:payload}
    python3 main.py more     [text]    # Universal Action "Plex" (→ on a row): the configured action
    python3 main.py back     [text]    # ↩ in the Text View (media sheet): the page it was opened from
"""

from __future__ import annotations

import sys
import time
from collections.abc import Mapping, Sequence

from . import alfred, plex
from .context import Context
from .system import failure, log, setup_logging

MODES = ("browse", "search", "discover", "grid", "prompt", "run", "more", "back")


def build_context(query: str, env: Mapping[str, str] | None = None) -> Context:
    ctx = Context.create(query=query, env=env)
    plex.bootstrap(ctx.settings)
    setup_logging(ctx.settings)
    return ctx


def render(mode: str, ctx: Context) -> str:
    if mode == "browse":
        from .views import render_browse

        return render_browse(ctx).to_json()
    if mode == "search":
        from .views.search import render_search

        return render_search(ctx).to_json()
    if mode == "grid":
        return render_grid_output(ctx)
    if mode == "prompt":
        from .views.prompt import render_prompt

        return render_prompt(ctx).to_json()
    from .views.discover import render_discover

    return render_discover(ctx).to_json()


def render_grid_output(ctx: Context) -> str:
    """The Grid View gets its items as the argument, and its column count as config."""
    import json

    from .views.grid import render_grid

    items = render_grid(ctx).to_json()
    return json.dumps({"alfredworkflow": {"arg": items, "config": {"columncount": ctx.settings.grid_columns}}},
                      ensure_ascii=False)


# Commands that can take a while: also notify, the user may have left Alfred.
LONG_COMMANDS = {"account.oauth", "account.sync", "devices.cleanup", "export", "logs.export", "media.download",
                 "server.logs", "server.databases", "server.install"}


def run_command(ctx: Context, text: str) -> str:
    """Execute ``{var:cmd}``; its status file feeds the loading page shown meanwhile."""
    from . import commands, runs, system

    name = ctx.var("cmd")
    run_id = ctx.var("run_id")
    system.MESSAGES.clear()
    system.QUIET = name not in LONG_COMMANDS
    runs.write(ctx.settings, run_id, state="running", started=time.time(), label=ctx.var("loading_label"))
    state = "done"
    try:
        intent = commands.execute(ctx, name, text)
    except plex.PlexError as error:
        failure(ctx.settings, str(error), error.__cause__ or error)
        intent, state = alfred.done(), "error"
    except Exception as error:  # noqa: BLE001 - tell the user instead of failing silently
        failure(ctx.settings, "Something went wrong, check the logs and create a GitHub issue", error)
        intent, state = alfred.done(), "error"
    intent = intent or alfred.done()
    if intent.action in alfred.NAV_ACTIONS and "back" not in intent.variables:
        # a page chosen by the command: Return goes back to where the user started
        intent.variables["back"] = alfred.history_json(ctx.history)
    if any(level == "error" for level, _ in system.MESSAGES):
        state = "error"
    runs.write(ctx.settings, run_id, state=state, messages=system.MESSAGES, next=intent.to_dict())
    return alfred.run_output(intent)


def more_output(ctx: Context, text: str) -> str:
    """→ on a row, then ↩ on "Plex" (Alfred's actions panel): the action chosen in the configuration.

    The text is the row's title: the media is found back in the rows of the last page shown. Any other text
    (the action is offered for every text in Alfred) is searched in Plex Search.
    """
    from .media import MORE_PREFIX
    from .system import log
    from .views import last_arrows, last_page

    text = text.strip()
    path = last_arrows(ctx).get(text)
    if path is None and text.startswith(MORE_PREFIX):
        path = text[len(MORE_PREFIX):]
    log.info("Right arrow on %r → %s (%s)", text, path or "Plex Search", ctx.settings.right_arrow)
    if path is None:
        intent = alfred.search(text)
        intent.variables["back"] = "[]"
        return alfred.run_output(intent)
    from .views.arrow import intent_for

    intent = intent_for(ctx, path)
    # Return (or ⎋ / ↩ in the media sheet) comes back to the results the row came from
    intent.variables["back"] = alfred.history_json(last_page(ctx))
    return alfred.run_output(intent)


def back_output(ctx: Context) -> str:
    """Leave the media sheet (Text View) for the page it was opened from (top of the history)."""
    intent = alfred.pop(ctx.history)
    if intent is None:
        intent = alfred.browse("")
        intent.variables["back"] = "[]"
    return alfred.run_output(intent)


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    mode = argv[0] if argv else "browse"
    if mode not in MODES:
        print(f"Unknown mode {mode!r}, expected one of {', '.join(MODES)}", file=sys.stderr)
        return 2
    text = argv[1] if len(argv) > 1 else ""
    ctx = build_context(text.strip() if mode not in {"run", "more", "back"} else "", env)
    log.debug("%s nav=%r cmd=%r query=%r", mode, ctx.nav, ctx.var("cmd"), ctx.query)
    if mode == "run":
        output = run_command(ctx, text)
    elif mode == "more":
        output = more_output(ctx, text)
    elif mode == "back":
        output = back_output(ctx)
    else:
        output = render(mode, ctx)
    sys.stdout.write(output)
    return 0
