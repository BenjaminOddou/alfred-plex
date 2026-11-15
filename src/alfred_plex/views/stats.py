"""Server statistics pages: live, libraries, plays, bandwidth, media quality."""

from __future__ import annotations

from datetime import datetime, timedelta

from .. import alfred, fmt, nav, stats
from ..alfred import Feedback, Item
from ..context import Context
from ..plex import parallel
from . import export_item, page

TOP = 5


def _path(mid: str, *sub: str) -> str:
    return nav.join("servers", mid, "stats", *sub)


@page("servers/<mid>/stats")
def stats_menu(ctx: Context, mid: str) -> list[Item]:
    days = ctx.settings.history_days
    entries = (
        ("Live", "Bandwidth, CPU and RAM, refreshed every second", "live", "bandwidth"),
        ("Libraries", "Items, size and duration of every library section", "libraries", "library"),
        ("Plays", f"Who watches what, where and when (last {days} days)", "plays", "history"),
        ("Bandwidth", f"Local / remote traffic per day, user and device (last {days} days)", "bandwidth",
         "bandwidth"),
        ("Media Quality", "4K, 1080p, 720p, SD and HDR per section", "quality", "movie"),
    )
    return [Item(t, s, intent=alfred.browse(_path(mid, p)), icon=alfred.icon(i)) for t, s, p, i in entries]


@page("servers/<mid>/stats/live")
def live(ctx: Context, mid: str) -> Feedback:
    plex = ctx.server(mid)
    since = datetime.now().replace(microsecond=0) - timedelta(seconds=2)
    total = local = 0
    for sample in plex.bandwidth(timespan="seconds", **{"at>": since}):
        total += sample.bytes or 0
        local += (sample.bytes or 0) if sample.lan else 0
    resources = plex.resources()
    usage = resources[-1] if resources else None
    items = [alfred.message("Server Bandwidth", f"Remote: {fmt.bitrate(total - local)} ǀ Local: {fmt.bitrate(local)}",
                            icon_name="bandwidth")]
    if usage:
        for label, process, host in (
            ("CPU Usage", usage.processCpuUtilization, usage.hostCpuUtilization),
            ("RAM Usage", usage.processMemoryUtilization, usage.hostMemoryUtilization),
        ):
            items.append(alfred.message(
                label, f"Plex {fmt.bar(process or 0, 100)} {fmt.percent(process)} ǀ "
                       f"System {fmt.bar(host or 0, 100)} {fmt.percent(host)}", icon_name="cpu_ram"))
    sessions = len(plex.sessions())
    items.append(Item("Sessions", f"{fmt.plural(sessions, 'stream')} playing right now",
                      intent=alfred.browse(nav.join("servers", mid, "sessions")), icon=alfred.icon("watch")))
    return Feedback(items, rerun=1)


@page("servers/<mid>/stats/libraries")
def libraries(ctx: Context, mid: str) -> list[Item]:
    plex = ctx.server(mid)
    totals = stats.storage_map(plex)
    rows = [r for r in parallel(lambda s: stats.library_rows([s], totals)[0], plex.library.sections(), workers=4)
            if not isinstance(r, Exception)]
    size = sum(r["size"] for r in rows)
    duration = sum(r["duration"] for r in rows)
    items = [
        alfred.message(f"{plex.friendlyName}: {fmt.size(size)}",
                       f"{fmt.plural(len(rows), 'section')} ǀ {fmt.hours(duration)} of media", icon_name="statistics"),
        export_item("libraries", "these numbers to a CSV file", mid=mid),
    ]
    for row in sorted(rows, key=lambda r: r["size"], reverse=True):
        counts = ", ".join(fmt.plural(n, kind) for kind, n in row["counts"].items())
        items.append(alfred.message(
            row["section"],
            fmt.join(counts, fmt.size(row["size"]), fmt.hours(row["duration"]) if row["duration"] else None,
                     f"{fmt.bar(row['size'], size)} {fmt.share(row['size'], size)} of the storage"),
            icon_name=row["type"] if row["type"] in {"movie", "show", "artist", "photo"} else "library",
        ))
    return items


def _ranking(title: str, counter, total: int, unit: str, icon: str, formatter=str) -> list[Item]:
    best = stats.top(counter, TOP)
    if not best:
        return []
    maximum = best[0][1]
    return [alfred.message(f"{title}: {formatter(name)}",
                           f"{fmt.bar(value, maximum)} {unit(value)} ({fmt.share(value, total)})", icon_name=icon)
            for name, value in best]


@page("servers/<mid>/stats/plays")
def plays(ctx: Context, mid: str) -> list[Item]:
    plex = ctx.server(mid)
    days = ctx.settings.history_days
    data = stats.plays(plex.history(mindate=fmt.since(days)), stats.Lookups.from_server(plex))
    if not data.total:
        return [alfred.message("No play", f"Nothing played during the last {days} days", icon_name="history")]
    per_day = round(data.total / days, 1)
    busiest = data.weekdays.most_common(1)[0][0] if data.weekdays else "-"
    hour = data.hours.most_common(1)[0][0] if data.hours else None
    count = lambda n: fmt.plural(n, "play")  # noqa: E731
    items = [
        alfred.message(f"{fmt.plural(data.total, 'play')} in {days} days",
                       fmt.join(f"{per_day} per day", f"Busiest day: {busiest}",
                                hour is not None and f"Peak hour: {hour:02d}:00",
                                ", ".join(f"{fmt.plural(n, t)}" for t, n in data.types.most_common())),
                       icon_name="statistics"),
        export_item("history", f"the {fmt.plural(data.total, 'play')} to a CSV file", mid=mid),
    ]
    items += _ranking("User", data.users, data.total, count, "person")
    items += _ranking("Title", data.titles, data.total, count, "movie")
    items += _ranking("Library", data.libraries, data.total, count, "library")
    items += _ranking("Device", data.devices, data.total, count, "device")
    items += _ranking("Platform", data.platforms, data.total, count, "device")
    return items


@page("servers/<mid>/stats/bandwidth")
def bandwidth(ctx: Context, mid: str) -> list[Item]:
    plex = ctx.server(mid)
    days = ctx.settings.history_days
    samples = plex.bandwidth(timespan="days", **{"at>": fmt.since(days)})
    data = stats.bandwidth(samples, stats.Lookups.from_server(plex))
    if not data.total:
        return [alfred.message("No traffic", f"No bandwidth recorded during the last {days} days",
                               icon_name="bandwidth")]
    items = [
        alfred.message(f"{fmt.size(data.total)} in {days} days",
                       f"Local {fmt.size(data.lan)} ({fmt.share(data.lan, data.total)}) ǀ "
                       f"Remote {fmt.size(data.wan)} ({fmt.share(data.wan, data.total)})", icon_name="bandwidth"),
        export_item("bandwidth", "the traffic per day, user and device to a CSV file", mid=mid),
    ]
    items += _ranking("User", data.users, data.total, fmt.size, "person")
    items += _ranking("Device", data.devices, data.total, fmt.size, "device")
    peak = max((sum(v) for v in data.days.values()), default=0)
    for day in sorted(data.days, reverse=True):
        lan, wan = data.days[day]
        items.append(alfred.message(
            day.strftime(ctx.settings.date_format),
            f"{fmt.bar(lan + wan, peak)} {fmt.size(lan + wan)} ǀ Local {fmt.size(lan)} ǀ Remote {fmt.size(wan)}",
            icon_name="history",
        ))
    return items


@page("servers/<mid>/stats/quality")
def quality(ctx: Context, mid: str) -> list[Item]:
    plex = ctx.server(mid)
    sections = [s for s in plex.library.sections() if s.type in stats.QUALITY_TYPES]
    if not sections:
        return [alfred.message("No movie or TV section on this server")]
    items = [export_item("quality", "the resolutions per section to a CSV file", mid=mid)]
    for section, result in zip(sections, parallel(stats.quality, sections, workers=4), strict=True):
        if isinstance(result, Exception) or not result:
            continue
        total = max(sum(v for k, v in result.items() if k != "HDR"), 1)
        for name, value in result.items():
            items.append(alfred.message(
                f"{section.title}: {name}",
                f"{fmt.bar(value, total)} {fmt.plural(value, stats.QUALITY_TYPES[section.type])} "
                f"({fmt.share(value, total)})",
                icon_name=section.type,
            ))
    return items
