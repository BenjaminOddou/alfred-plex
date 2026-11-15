"""Help commands: alias edition, folders cleanup."""

from __future__ import annotations

from ..context import Context
from ..store import Alias, AliasEntry
from ..system import clear_folder, success, warning
from . import command


@command("alias.edit")
def edit_alias(ctx: Context, text: str) -> None:
    long_key, short = ctx.payload["long"], text.strip()
    alias = ctx.store.alias
    if not short or "=" in short or "/" in short:
        warning(ctx.settings, "An alias can't be empty or contain '=' or '/'")
        return
    owner = next((e.long for e in alias.entries if e.short == short and e.long != long_key), None)
    if owner:
        warning(ctx.settings, f"The alias {short} is already used for {owner}")
        return
    entries = [AliasEntry(short if e.long == long_key else e.short, e.long) for e in alias.entries]
    ctx.store.save_alias(Alias(entries, alias.enabled))
    success(ctx.settings, f"Alias of {long_key} is now {short}")


@command("alias.reset")
def reset_alias(ctx: Context, text: str) -> None:
    ctx.store.reset_alias()
    success(ctx.settings, "The alias file is reset")


@command("folder.clear")
def clear(ctx: Context, text: str) -> None:
    kind = ctx.payload["kind"]
    if kind == "cache":
        count = clear_folder(ctx.settings.cache_dir, keep=("version",))
    else:
        # Presets are personal work: they survive a data cleanup (same as v2).
        count = clear_folder(ctx.settings.data_dir, keep=("presets.json",))
    success(ctx.settings, f"{kind.capitalize()} folder cleared ({count} file(s) removed)")
