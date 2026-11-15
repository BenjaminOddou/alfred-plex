"""Side effects on the Mac: logging, notifications, opening things."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .settings import Settings

log = logging.getLogger("alfred_plex")

# Messages of the current command, shown by the loading page: [(level, text)]
MESSAGES: list[tuple[str, str]] = []
# Quick commands answer in Alfred (loading page) only; long ones also notify (you may have left).
QUIET = False

# Alfred runs scripts with a minimal PATH: add Homebrew so vlc / iina CLIs are found.
EXTRA_PATHS = ("/opt/homebrew/bin", "/usr/local/bin")


def setup_logging(settings: Settings) -> None:
    if log.handlers:
        return
    handler = RotatingFileHandler(
        settings.cache_dir / "plex.log", maxBytes=512_000, backupCount=2, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s", f"{settings.date_format} %H:%M:%S")
    )
    log.addHandler(handler)
    log.setLevel(getattr(logging, settings.log_level, logging.INFO))
    log.propagate = False


def notify(settings: Settings, title: str, message: str) -> None:
    """Show a macOS notification with the workflow icon (via Notificator).

    Arguments are passed as a list, never through a shell, so titles coming
    from Plex (``$(...)``, quotes...) cannot inject commands.
    """
    cmd = [str(settings.workflow_dir / "notificator"), "--message", message, "--title", title]
    if settings.sound:
        cmd += ["--sound", settings.sound]
    try:
        _spawn(cmd)
    except (OSError, subprocess.SubprocessError) as error:
        log.warning("Notification failed: %s", error)


def _spawn(cmd: list[str]) -> None:
    subprocess.run(cmd, check=False, capture_output=True, timeout=30)


def success(settings: Settings, message: str) -> None:
    MESSAGES.append(("success", message))
    log.info(message)
    if not QUIET:
        notify(settings, "✅ Success!", message)


def warning(settings: Settings, message: str) -> None:
    MESSAGES.append(("warning", message))
    log.warning(message)
    if not QUIET:
        notify(settings, "⚠️ Warning!", message)


def failure(settings: Settings, message: str, error: BaseException | None = None) -> None:
    MESSAGES.append(("error", message))
    if error is not None:
        log.error("%s: %r", message, error, exc_info=error)
    else:
        log.error(message)
    notify(settings, "🚨 Error!", message)


def search_path() -> str:
    paths = os.environ.get("PATH", "").split(os.pathsep)
    return os.pathsep.join([p for p in EXTRA_PATHS if p not in paths] + paths)


def which(program: str) -> str | None:
    return shutil.which(program, path=search_path())


def open_in_background(target: str) -> None:
    subprocess.run(["open", target], check=False)


def clear_folder(folder: Path, keep: tuple[str, ...] = ()) -> int:
    """Delete regular files of ``folder`` (sub-folders such as Notificator.app are kept)."""
    removed = 0
    if not folder.is_dir():
        return removed
    for path in folder.iterdir():
        if path.is_file() and path.name not in keep:
            path.unlink()
            removed += 1
            log.info("%s removed", path)
    return removed
