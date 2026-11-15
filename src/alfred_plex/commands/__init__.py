"""Background commands executed by ``main.py run``.

A command receives the context (``ctx.payload`` holds its parameters) and
the text typed by the user (for prompts). It may return the next
:class:`~alfred_plex.alfred.Intent`; otherwise the ``then`` intent given by
the page is used.
"""

from __future__ import annotations

from collections.abc import Callable

from ..alfred import Intent
from ..context import Context

Command = Callable[[Context, str], "Intent | None"]
COMMANDS: dict[str, Command] = {}


def command(name: str) -> Callable[[Command], Command]:
    def decorator(func: Command) -> Command:
        COMMANDS[name] = func
        return func

    return decorator


def load() -> dict[str, Command]:
    from . import accounts, exports, help, media, presets, servers  # noqa: F401 - registration

    return COMMANDS


def then(ctx: Context) -> Intent | None:
    return Intent.from_dict(ctx.payload.get("_then"))


def execute(ctx: Context, name: str, text: str = "") -> Intent | None:
    handler = load().get(name)
    if handler is None:
        raise KeyError(f"Unknown command: {name}")
    result = handler(ctx, text)
    return result if result is not None else then(ctx)
