"""Side effects on the Mac: logging, command messages, sounds, opening things."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from .settings import Settings

log = logging.getLogger("alfred_plex")

# Messages of the current command: [(level, text)]. The loading page shows them, and long commands sum them
# up in a notification posted by Alfred (Post Notification output, after the Run Script).
MESSAGES: list[tuple[str, str]] = []
TITLES = {"success": "✅ Success!", "warning": "⚠️ Warning!", "error": "🚨 Error!"}
SOUNDS = Path("/System/Library/Sounds")
LOG_SIZE = 512_000

# Alfred runs scripts with a minimal PATH: add Homebrew so vlc / iina CLIs are found.
EXTRA_PATHS = ("/opt/homebrew/bin", "/usr/local/bin")


def setup_logging(settings: Settings) -> None:
    """``plex.log`` in the cache folder, rotated at startup (cheaper than ``logging.handlers``)."""
    if log.handlers:
        return
    path = settings.cache_dir / "plex.log"
    try:
        if path.stat().st_size > LOG_SIZE:
            os.replace(path, path.with_name("plex.log.1"))
    except OSError:
        pass
    handler = logging.FileHandler(path, encoding="utf-8", delay=True)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s", f"{settings.date_format} %H:%M:%S")
    )
    log.addHandler(handler)
    log.setLevel(getattr(logging, settings.log_level, logging.INFO))
    log.propagate = False


def success(message: str) -> None:
    MESSAGES.append(("success", message))
    log.info(message)


def warning(message: str) -> None:
    MESSAGES.append(("warning", message))
    log.warning(message)


def failure(message: str, error: BaseException | None = None) -> None:
    MESSAGES.append(("error", message))
    if error is not None:
        log.error("%s: %r", message, error, exc_info=error)
    else:
        log.error(message)


def notification(messages: list[tuple[str, str]]) -> tuple[str, str]:
    """(title, text) of the notification that sums up a command: the worst level gives the title."""
    if not messages:
        return "", ""
    levels = {level for level, _ in messages}
    level = "error" if "error" in levels else "warning" if "warning" in levels else "success"
    return TITLES[level], " ǀ ".join(text for _, text in messages)


def play(sound: str) -> None:
    """Play a macOS system sound (``sound`` setting) without waiting for it."""
    path = SOUNDS / f"{sound}.aiff"
    if not sound or not path.is_file():
        return
    try:
        _detach(["afplay", str(path)])
    except OSError as error:
        log.warning("Sound failed: %s", error)


def _detach(cmd: list[str]) -> None:
    import subprocess

    subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


def search_path() -> str:
    paths = os.environ.get("PATH", "").split(os.pathsep)
    return os.pathsep.join([p for p in EXTRA_PATHS if p not in paths] + paths)


def which(program: str) -> str | None:
    import shutil

    return shutil.which(program, path=search_path())


def open_in_background(target: str) -> None:
    import subprocess

    subprocess.run(["open", target], check=False)


def clear_folder(folder: Path, keep: tuple[str, ...] = ()) -> int:
    """Delete the regular files of ``folder`` (sub-folders such as ``posters`` are kept)."""
    removed = 0
    if not folder.is_dir():
        return removed
    for path in folder.iterdir():
        if path.is_file() and path.name not in keep:
            path.unlink()
            removed += 1
            log.info("%s removed", path)
    return removed
