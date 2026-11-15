"""Small formatting helpers (pure functions, easy to test)."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta

SEP = " ǀ "


def join(*parts: object) -> str:
    """Join non-empty parts with the workflow separator."""
    return SEP.join(str(p) for p in parts if p not in (None, "", [], ()))


def duration(milliseconds: int | None) -> str:
    if not milliseconds:
        return ""
    total = int(milliseconds) // 1000
    hours, rest = divmod(total, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def day(value: datetime | date | None, fmt: str = "%Y-%m-%d") -> str:
    return value.strftime(fmt) if value else ""


def size(num_bytes: int | None, decimals: int = 2) -> str:
    if not num_bytes or num_bytes <= 0:
        return "0 B"
    units = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    index = min(int(math.floor(math.log(num_bytes, 1024))), len(units) - 1)
    return f"{round(num_bytes / 1024 ** index, decimals)} {units[index]}"


def bitrate(bytes_per_second: float) -> str:
    bits = bytes_per_second * 8
    for unit, factor in (("Gbps", 1024**3), ("Mbps", 1024**2), ("Kbps", 1024)):
        if bytes_per_second >= factor:
            return f"{round(bits / factor, 2)} {unit}"
    return f"{round(bits, 2)} bps"


def percent(value: float | None) -> str:
    return f"{round(value or 0, 2)}%"


def plural(count: int | None, word: str, many: str | None = None) -> str:
    count = count or 0
    return f"{count} {word if count == 1 else (many or word + 's')}"


def since(days: int) -> datetime:
    return datetime.now() - timedelta(days=days)


def year(value: object) -> str:
    return f" ({value})" if value else ""


def ago(value: datetime | None, now: datetime | None = None) -> str:
    """Human delay: ``today``, ``yesterday``, ``12 days ago``, ``3 months ago``..."""
    if not value:
        return "never"
    now = now or datetime.now(value.tzinfo)
    days = (now - value).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 60:
        return f"{days} days ago"
    if days < 730:
        return f"{days // 30} months ago"
    return f"{days // 365} years ago"


def days_since(value: datetime | None, now: datetime | None = None) -> int:
    """Days elapsed since ``value`` (a very big number when unknown)."""
    if not value:
        return 10**6
    now = now or datetime.now(value.tzinfo)
    return (now - value).days


def bar(value: float, maximum: float, width: int = 10) -> str:
    """Tiny text bar for Alfred subtitles: ``██████░░░░``."""
    if maximum <= 0:
        return "░" * width
    filled = round(width * max(0.0, min(1.0, value / maximum)))
    return "█" * filled + "░" * (width - filled)


def share(value: float, total: float) -> str:
    return f"{round(100 * value / total)}%" if total else "0%"


def hours(milliseconds: int | None) -> str:
    """Long durations: ``1 234 h``."""
    return f"{round((milliseconds or 0) / 3_600_000):,} h".replace(",", " ")
