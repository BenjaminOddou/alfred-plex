"""Plex Presets pages."""

from __future__ import annotations

from .. import alfred, fmt, nav
from ..alfred import Item, Mod
from ..context import Context
from ..filters import FILTER_SPLIT
from . import export_item, page


def display_value(ctx: Context, value: str) -> tuple[str, list[str]]:
    """Rewrite a preset with the names the user sees (alias or long). Returns unknown keys too."""
    alias = ctx.store.alias
    chunks, unknown = [], []
    for chunk in FILTER_SPLIT.split(value or ""):
        key, sep, rest = chunk.partition("=")
        name = alias.resolve(key) if sep else None
        if sep and not name:
            unknown.append(key.strip())
        chunks.append(f"{alias.display(name)}={rest}" if name else chunk)
    return "/".join(chunks), unknown


def _remove(preset: dict, back) -> object:
    return alfred.confirm(f"Delete the preset {preset.get('title')}?", preset.get("arg", ""),
                          alfred.run("preset.remove", then=back, id=preset.get("id")))


@page("presets")
def presets(ctx: Context) -> list[Item]:
    here = alfred.browse("presets")
    saved = ctx.store.presets.items
    items = [
        Item("Add a new preset", "Tip: in Plex Search, the last row saves your current search as a preset",
             intent=alfred.ask("Preset Value",
                               "Search options separated by a '/' ǀ Example: libtype=movie/title=Matrix",
                               "preset.new_value"),
             icon=alfred.icon("add")),
    ]
    for index, preset in enumerate(saved):
        value, unknown = display_value(ctx, preset.get("arg", ""))
        subtitle = preset.get("subtitle", "") or value
        if unknown:
            subtitle = f"⚠️ Unknown filter(s): {', '.join(unknown)} ǀ {subtitle}"
        preset_id = preset.get("id", "")
        mods = {
            "cmd": Mod("Edit, duplicate, reorder or delete this preset",
                       alfred.browse(nav.join("presets", preset_id)), alfred.icon("modify")),
            "alt": Mod("Delete this preset", _remove(preset, here), alfred.icon("delete")),
            "ctrl": Mod("Duplicate this preset", alfred.run("preset.duplicate", then=here, id=preset_id),
                        alfred.icon("add")),
        }
        if index:
            mods["shift"] = Mod("Move this preset up", alfred.run("preset.move", then=here, id=preset_id, offset=-1),
                                alfred.icon("sort"))
        items.append(Item(preset.get("title", ""), f"{subtitle}  ·  ⌘ edit ⌥ delete ⌃ duplicate ⇧ move up",
                          intent=alfred.search(value), icon=alfred.icon("preset"), mods=mods, text=value))
    if saved:
        items.append(export_item("presets", f"your {fmt.plural(len(saved), 'preset')} to a CSV file"))
    return items


@page("presets/<preset_id>")
def modify(ctx: Context, preset_id: str) -> list[Item]:
    preset = ctx.store.presets.get(preset_id)
    if not preset:
        return [alfred.message("This preset does not exist anymore")]
    here = alfred.browse(nav.join("presets", preset_id))
    title, subtitle, value = preset.get("title", ""), preset.get("subtitle", ""), preset.get("arg", "")
    shown, _ = display_value(ctx, value)
    return [
        Item(f"Search: {title}", shown, intent=alfred.search(shown), icon=alfred.icon("folder")),
        Item("Modify the Preset's Title/Subtitle", f"Current Title: {title} ǀ Current Subtitle: {subtitle}",
             intent=alfred.ask("Preset Title/Subtitle", f"Use a '/' to separate them ǀ Current: {title}/{subtitle}",
                               "preset.edit_title", then=here, id=preset_id),
             icon=alfred.icon("preset"), text=f"{title}/{subtitle}"),
        Item("Modify the Preset's Value", f"Current Value: {value} ǀ ⌘C copies it",
             intent=alfred.ask("Preset Value", f"Current: {value}", "preset.edit_value", then=here, id=preset_id),
             icon=alfred.icon("preset"), text=value),
        Item("Duplicate", "Create a copy to make a variant of this search",
             intent=alfred.run("preset.duplicate", then=alfred.browse("presets"), id=preset_id),
             icon=alfred.icon("add")),
        Item("Move up", "Show this preset higher in the list",
             intent=alfred.run("preset.move", then=here, id=preset_id, offset=-1), icon=alfred.icon("sort")),
        Item("Move down", "Show this preset lower in the list",
             intent=alfred.run("preset.move", then=here, id=preset_id, offset=1), icon=alfred.icon("sort")),
        Item("Delete", "Remove this preset", intent=_remove(preset, alfred.browse("presets")),
             icon=alfred.icon("delete")),
    ]
