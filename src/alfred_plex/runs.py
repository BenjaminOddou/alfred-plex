"""Status of background commands, read by the loading page.

``main.py run`` writes ``cache/runs/<run_id>.json`` when a command starts and
when it ends (messages + next step). The loading page polls it, so Alfred
stays open with a progress row instead of closing during long requests.
"""

from __future__ import annotations

import time
from pathlib import Path

from .settings import Settings
from .store import read_json, write_json

KEEP_SECONDS = 24 * 3600


def path(settings: Settings, run_id: str) -> Path:
    safe = "".join(c for c in run_id if c.isalnum())[:32] or "none"
    return settings.cache_dir / "runs" / f"{safe}.json"


def read(settings: Settings, run_id: str) -> dict | None:
    if not run_id:
        return None
    data = read_json(path(settings, run_id), None)
    return data if isinstance(data, dict) else None


def write(settings: Settings, run_id: str, **data) -> None:
    if not run_id:
        return
    target = path(settings, run_id)
    write_json(target, {"time": time.time(), **data})
    for old in target.parent.glob("*.json"):
        if time.time() - old.stat().st_mtime > KEEP_SECONDS:
            old.unlink(missing_ok=True)
