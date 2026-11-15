"""Export commands: CSV files and the workflow logs archive."""

from __future__ import annotations

from .. import alfred, export
from ..alfred import Intent
from ..context import Context
from ..system import notify, success, warning
from . import command


@command("export")
def export_csv(ctx: Context, text: str) -> Intent | None:
    params = dict(ctx.payload)
    kind = params.pop("kind", "")
    if kind not in export.EXPORTERS:
        warning(ctx.settings, f"Unknown export: {kind}")
        return None
    notify(ctx.settings, "⏳ Please wait!", f"Exporting {kind}...")
    path, count = export.export(ctx, kind, params)
    success(ctx.settings, f"{count} row(s) exported to {path.name}")
    return alfred.reveal(str(path))


@command("logs.export")
def export_logs(ctx: Context, text: str) -> Intent:
    path = export.logs_archive(ctx)
    success(ctx.settings, f"Logs saved to {path.name}: attach it to your GitHub issue")
    return alfred.reveal(str(path))
