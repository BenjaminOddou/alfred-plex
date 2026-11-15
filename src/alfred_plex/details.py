"""Full media sheet rendered as Markdown for Alfred's Text View.

The file is written in the cache folder next to the posters, so the poster
is referenced with a relative path (Text View resolves image paths from the
folder of the file).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import fmt

RATING_SOURCES = {
    "rottentomatoes": "Rotten Tomatoes",
    "imdb": "IMDb",
    "themoviedb": "TMDB",
    "thetvdb": "TVDB",
}
MAX_CAST = 12


def human_duration(milliseconds: int | None) -> str:
    if not milliseconds:
        return ""
    minutes = int(milliseconds) // 60000
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes} min"


def _names(tags: Any, limit: int = 8) -> str:
    names = [t.tag for t in tags or [] if getattr(t, "tag", None)]
    return ", ".join(names[:limit]) + ("…" if len(names) > limit else "")


def _source(image: str | None) -> str:
    provider = (image or "").split("://", 1)[0]
    return RATING_SOURCES.get(provider, "")


def _escape(text: object) -> str:
    return str(text).replace("\n", " ")


def _table(rows: list[tuple[str, Any]]) -> list[str]:
    """``- **Name:** value`` lines (Alfred's Text View doesn't render Markdown tables)."""
    rows = [(k, v) for k, v in rows if v not in (None, "", [], ())]
    if not rows:
        return []
    return [*[f"- **{k}:** {_escape(v)}" for k, v in rows], ""]


def _ids(media: Any) -> str:
    labels = {"tmdb": "TMDB", "imdb": "IMDb", "tvdb": "TVDB"}
    found = []
    for guid in getattr(media, "guids", None) or []:
        provider, _, value = str(guid.id).partition("://")
        if provider in labels:
            found.append(f"{labels[provider]} {value}")
    return " · ".join(found)


def _streams(part: Any, kind: str) -> str:
    method = {"video": part.videoStreams, "audio": part.audioStreams, "subtitle": part.subtitleStreams}[kind]
    return ", ".join(s.displayTitle or s.title or s.codec or "?" for s in method())


def _files(media: Any) -> list[str]:
    lines = []
    for version in getattr(media, "media", None) or []:
        for part in version.parts:
            name = Path(part.file or "").name or f"Part {part.id}"
            lines += [f"### 📄 {_escape(name)}", ""]
            lines += _table([
                ("Size", fmt.size(part.size) if part.size else ""),
                ("Container", part.container or version.container),
                ("Video", fmt.join(_streams(part, "video"), version.bitrate and f"{version.bitrate} kbps")),
                ("Audio", _streams(part, "audio")),
                ("Subtitles", _streams(part, "subtitle")),
                ("Path", f"`{part.file}`" if part.file else ""),
            ])
    return lines


def sheet(media: Any, kind: str, label: str, server: str, poster: str | None, date_format: str) -> str:
    """Markdown describing ``media`` (works for movies, shows, seasons, episodes, albums, tracks)."""
    g = lambda name: getattr(media, name, None)  # noqa: E731
    lines: list[str] = []
    if poster:
        lines += [f"![Poster]({poster})", ""]
    lines += [f"# {label}", ""]
    if g("tagline"):
        lines += [f"*{g('tagline')}*", ""]
    if kind == "episode":
        lines += [f"**{g('grandparentTitle')}** › {g('parentTitle')} › Episode {g('index')}", ""]
    counts = None
    if kind == "show":
        counts = fmt.join(fmt.plural(g("childCount"), "season"), fmt.plural(g("leafCount"), "episode"))
    elif kind in {"season", "album"}:
        counts = fmt.plural(g("leafCount"), "episode" if kind == "season" else "track")
    lines.append(" · ".join(str(p) for p in (
        f"**{kind.capitalize()}**", human_duration(g("duration")), counts, g("contentRating"), g("studio"),
        g("originallyAvailableAt") and f"Released {fmt.day(g('originallyAvailableAt'), date_format)}",
    ) if p))
    ratings = [
        g("audienceRating") and f"⭐ Audience {g('audienceRating')}/10 {_source(g('audienceRatingImage'))}".strip(),
        g("rating") and f"Critics {g('rating')}/10 {_source(g('ratingImage'))}".strip(),
        g("userRating") and f"Your rating {g('userRating')}/10",
    ]
    if any(ratings):
        lines += ["", " · ".join(r for r in ratings if r)]
    played = "✓ Played" if g("isPlayed") else ("◐ In progress" if g("viewOffset") else "Not played")
    lines += ["", " · ".join(p for p in (
        played, g("viewCount") and f"{fmt.plural(g('viewCount'), 'view')}",
        g("lastViewedAt") and f"last viewed {fmt.ago(g('lastViewedAt'))}",
        g("addedAt") and f"added {fmt.day(g('addedAt'), date_format)}",
    ) if p), ""]
    if g("summary"):
        lines += [g("summary").strip(), ""]

    roles = list(g("roles") or [])
    if roles:
        lines += ["## 🎭 Cast", ""]
        lines += [f"- **{r.tag}**" + (f" as {r.role}" if getattr(r, "role", None) else "") for r in roles[:MAX_CAST]]
        if len(roles) > MAX_CAST:
            lines.append(f"- … and {len(roles) - MAX_CAST} more")
        lines.append("")
    crew = _table([("Directors", _names(g("directors"))), ("Writers", _names(g("writers"))),
                   ("Producers", _names(g("producers")))])
    if crew:
        lines += ["## 🎬 Crew", "", *crew]
    info = _table([
        ("Genres", _names(g("genres"))), ("Countries", _names(g("countries"))),
        ("Collections", _names(g("collections"))), ("Labels", _names(g("labels"))),
        ("Edition", g("editionTitle")), ("Library", fmt.join(g("librarySectionTitle"), server)),
        ("IDs", _ids(media)),
    ])
    if info:
        lines += ["## ℹ️ Details", "", *info]
    files = _files(media)
    if files:
        lines += ["## 💾 Files", "", *files]
    return "\n".join(lines).rstrip() + "\n"


def write(cache_dir: Path, name: str, text: str) -> Path:
    folder = cache_dir / "details"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.md"
    path.write_text(text, encoding="utf-8")
    return path


def prepare(ctx: Any, server: Any, media: Any, mid: str) -> Path:
    """Poster + Markdown sheet of ``media`` in the cache; returns the file shown by the Text View."""
    from . import posters
    from .media import CLASSES, title

    kind = CLASSES.get(type(media).__name__, (media.type, ""))[0]
    poster = posters.server_posters(ctx.settings, server, [media]).get(str(media.ratingKey))
    relative = f"../posters/{poster.name}" if poster else None
    saved = ctx.store.server(mid) or {}
    text = sheet(media, kind, title(media, kind), saved.get("friendlyName", ""), relative, ctx.settings.date_format)
    return write(ctx.settings.cache_dir, f"{mid}-{media.ratingKey}", text)


# ---------------------------------------------------------------- discover
def discover_sheet(element: Any, kind: str, label: str, poster: str | None) -> str:
    """Markdown sheet of a Plex Discover movie / show (XML metadata from metadata.provider.plex.tv)."""
    a = (element.attrib if element is not None else {}).get
    tags = lambda tag: ", ".join(e.attrib.get("tag", "") for e in (element.iter(tag) if element is not None else [])
                                 if e.attrib.get("tag"))  # noqa: E731
    lines: list[str] = []
    if poster:
        lines += [f"![Poster]({poster})", ""]
    lines += [f"# {label}", ""]
    if a("tagline"):
        lines += [f"*{a('tagline')}*", ""]
    duration = human_duration(int(a("duration"))) if str(a("duration") or "").isdigit() else ""
    seasons = fmt.plural(a("childCount"), "season") if kind == "show" and a("childCount") else ""
    lines.append(" · ".join(p for p in (
        f"**{kind.capitalize()}**", duration, seasons, a("contentRating"), a("studio"),
        a("originallyAvailableAt") and f"Released {a('originallyAvailableAt')}", "Plex Discover",
    ) if p))
    ratings = [a("audienceRating") and f"⭐ Audience {a('audienceRating')}/10",
               a("rating") and f"Critics {a('rating')}/10"]
    if any(ratings):
        lines += ["", " · ".join(r for r in ratings if r)]
    lines.append("")
    if a("summary"):
        lines += [a("summary").strip(), ""]
    roles = list(element.iter("Role")) if element is not None else []
    if roles:
        lines += ["## 🎭 Cast", ""]
        for role in roles[:MAX_CAST]:
            character = role.attrib.get("role")
            lines.append(f"- **{role.attrib.get('tag', '')}**" + (f" as {character}" if character else ""))
        if len(roles) > MAX_CAST:
            lines.append(f"- … and {len(roles) - MAX_CAST} more")
        lines.append("")
    crew = _table([("Directors", tags("Director")), ("Writers", tags("Writer"))])
    if crew:
        lines += ["## 🎬 Crew", "", *crew]
    ids = " · ".join(
        f"{name} {value}" for provider, name in (("tmdb", "TMDB"), ("imdb", "IMDb"), ("tvdb", "TVDB"))
        for guid in (element.iter("Guid") if element is not None else [])
        for p, _, value in [str(guid.attrib.get("id", "")).partition("://")] if p == provider)
    info = _table([("Genres", tags("Genre")), ("Countries", tags("Country")), ("IDs", ids)])
    if info:
        lines += ["## ℹ️ Details", "", *info]
    return "\n".join(lines).rstrip() + "\n"
