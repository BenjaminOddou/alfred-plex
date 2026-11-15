"""Preset commands (create, edit, delete)."""

from __future__ import annotations

from .. import alfred
from ..alfred import Intent
from ..context import Context
from ..system import success, warning
from . import command, then


def split_title(text: str) -> tuple[str, str]:
    title, _, subtitle = text.partition("/")
    return title.strip(), subtitle.strip()


@command("preset.new_value")
def new_value(ctx: Context, text: str) -> Intent:
    value = text.strip()
    if not value:
        warning(ctx.settings, "A preset needs a value")
        return alfred.browse("presets")
    return alfred.ask("Preset Title/Subtitle", "Input a title and a description ǀ Example: My Preset/Some description",
                      "preset.new_title", then=alfred.browse("presets"), value=value)


@command("preset.new_title")
def new_title(ctx: Context, text: str) -> None:
    title, subtitle = split_title(text)
    if not title:
        warning(ctx.settings, "A preset needs a title")
        return
    ctx.store.presets.upsert({"title": title, "subtitle": subtitle, "arg": ctx.payload["value"],
                              "id": ctx.store.new_id()})
    ctx.store.presets.save()
    success(ctx.settings, f"The preset {title} is created")


def _edit(ctx: Context, **changes: str) -> None:
    preset = ctx.store.presets.get(ctx.payload["id"])
    if not preset:
        warning(ctx.settings, "This preset does not exist anymore")
        return
    preset.update(changes)
    ctx.store.presets.save()
    success(ctx.settings, f"The preset {preset['title']} is modified")


@command("preset.edit_title")
def edit_title(ctx: Context, text: str) -> None:
    title, subtitle = split_title(text)
    if not title:
        warning(ctx.settings, "A preset needs a title")
        return
    _edit(ctx, title=title, subtitle=subtitle)


@command("preset.edit_value")
def edit_value(ctx: Context, text: str) -> None:
    if not text.strip():
        warning(ctx.settings, "A preset needs a value")
        return
    _edit(ctx, arg=text.strip())


@command("preset.remove")
def remove(ctx: Context, text: str) -> Intent | None:
    removed = ctx.store.presets.remove(ctx.payload["id"])
    ctx.store.presets.save()
    if removed:
        success(ctx.settings, f"The preset {removed[0].get('title')} is removed")
    return then(ctx) if ctx.store.presets.items else alfred.browse("presets")


@command("preset.duplicate")
def duplicate(ctx: Context, text: str) -> None:
    items = ctx.store.presets.items
    preset = ctx.store.presets.get(ctx.payload["id"])
    if not preset:
        warning(ctx.settings, "This preset does not exist anymore")
        return
    copy = {**preset, "title": f"{preset.get('title', '')} (copy)", "id": ctx.store.new_id()}
    items.insert(items.index(preset) + 1, copy)
    ctx.store.presets.save()
    success(ctx.settings, f"The preset {preset.get('title')} is duplicated")


@command("preset.move")
def move(ctx: Context, text: str) -> None:
    items = ctx.store.presets.items
    preset = ctx.store.presets.get(ctx.payload["id"])
    if not preset:
        return
    index = items.index(preset)
    target = max(0, min(len(items) - 1, index + int(ctx.payload.get("offset", -1))))
    items.insert(target, items.pop(index))
    ctx.store.presets.save()


@command("preset.save")
def save_search(ctx: Context, text: str) -> None:
    """Save the current Plex Search query (from the last row of the results)."""
    title, subtitle = split_title(text)
    if not title:
        warning(ctx.settings, "A preset needs a title")
        return
    ctx.store.presets.upsert({"title": title, "subtitle": subtitle, "arg": ctx.payload["value"],
                              "id": ctx.store.new_id()})
    ctx.store.presets.save()
    success(ctx.settings, f"The preset {title} is saved: find it in Plex Presets")
