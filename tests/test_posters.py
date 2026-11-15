"""3.2 features: Grid View posters, library browser (sort / filter by picking), media details sheet."""

from __future__ import annotations

import json
from pathlib import Path

import fakes
from conftest import came_from, make_ctx
from test_commands import run
from test_views import by_title, page, titles

from alfred_plex import alfred, cli, details, nav, posters

LIBRARY = nav.join("library", fakes.MID, 1)


def grid(env, path: str, **variables) -> tuple[dict, list[dict]]:
    """Render a Grid View page like Alfred: (config, items)."""
    ctx = make_ctx(env, nav=path, **variables)
    output = json.loads(cli.render("grid", ctx))["alfredworkflow"]
    return output["config"], json.loads(output["arg"])["items"]


# ------------------------------------------------------------ library browser
def test_libraries_list_every_section(env, plex_online):
    items = page(env, "library")
    assert titles(items) == ["Return", "Movies", "TV Shows", "Music"]
    movies = items[1]
    assert movies["variables"]["nav"] == LIBRARY
    assert movies["mods"]["cmd"]["variables"]["action"] == "grid"


def test_library_page(env, plex_online):
    items = page(env, LIBRARY)
    assert items[1]["title"] == "Movies: 2 movies"
    assert "Sort: Date Added ↓" in items[1]["subtitle"] and "Filters: none" in items[1]["subtitle"]
    names = titles(items)
    assert names[2:5] == ["🖼️ Show as posters", "↕️ Sort: Date Added ↓", "➕ Add a filter"]
    assert by_title(items, "🔍 Open in Plex Search")["arg"] == "sc=Movies/lt=movie/so=addedAt:desc"
    assert names[-2:] == ["The Matrix (1999)", "Inception (2010)"]
    grid_state = json.loads(by_title(items, "🖼️ Show as posters")["variables"]["state"])
    assert grid_state["view"] == "grid"


def test_pick_a_sort(env, plex_online):
    items = page(env, nav.join("library", fakes.MID, 1, "sort"), state=json.dumps({"sort": "addedAt:desc"}))
    assert titles(items)[1:4] == ["Release Date", "Title", "✓ Date Added"]
    title_row = by_title(items, "Title")
    assert json.loads(title_row["variables"]["state"])["sort"] == "titleSort:asc"
    assert json.loads(title_row["mods"]["cmd"]["variables"]["state"])["sort"] == "titleSort:desc"
    assert title_row["variables"]["nav"] == LIBRARY


def test_pick_filters(env, plex_online):
    filters = page(env, nav.join("library", fakes.MID, 1, "filter"))
    unplayed = by_title(filters, "Unplayed")
    assert json.loads(unplayed["variables"]["state"])["filters"] == {"unwatched": 1}
    genre = by_title(filters, "Genre")
    assert genre["variables"]["nav"] == nav.join("library", fakes.MID, 1, "filter", "genre")
    choices = page(env, genre["variables"]["nav"])
    action = by_title(choices, "Action")
    state = json.loads(action["variables"]["state"])
    assert state["filters"] == {"genre": "12"} and state["labels"] == {"genre": "Genre: Action"}


def test_library_with_filters(env, plex_online):
    state = {"sort": "titleSort:asc", "filters": {"genre": "12", "unwatched": 1},
             "labels": {"genre": "Genre: Action", "unwatched": "Unplayed"}}
    items = page(env, LIBRARY, state=json.dumps(state))
    assert "Filters: Genre: Action · Unplayed" in items[1]["subtitle"]
    remove = by_title(items, "✖ Genre: Action")
    assert json.loads(remove["variables"]["state"])["filters"] == {"unwatched": 1}
    assert "🧹 Clear all filters" in titles(items)
    assert by_title(items, "🔍 Open in Plex Search")["arg"] == "sc=Movies/lt=movie/ge=12/uw=1/so=titleSort:asc"
    searches = [q for _, path, q in plex_online.calls if path == "/library/sections/1/all" and "sort" in q]
    assert searches and searches[-1]["genre"] == "12" and searches[-1]["sort"] == "movie.titleSort:asc"


# ------------------------------------------------------------------ grid view
def test_grid_library_posters(env, plex_online):
    config, items = grid({**env, "grid_columns": "7"}, nav.join("grid", "library", fakes.MID, 1),
                         state=json.dumps({"view": "grid"}))
    assert config == {"columncount": 7}
    assert titles(items)[:4] == ["Return", "↕️ Date Added ↓", "➕ Filter", "☰ List view"]
    assert items[0]["variables"]["action"] == "search"  # no history: Plex Search (where libraries live)
    matrix = by_title(items, "The Matrix (1999)")
    poster = Path(matrix["icon"]["path"])
    assert poster.is_absolute() and poster.read_bytes() == b"JPEG-BYTES"
    assert poster.parent == Path(env["alfred_workflow_cache"]) / "posters"
    assert matrix["variables"]["action"] == "browse"
    assert nav.split(matrix["variables"]["nav"]) == ["media", fakes.MID, "10"]
    assert came_from(matrix["variables"]).action == "grid"  # Return comes back to the posters
    assert matrix["mods"]["alt"]["variables"]["cmd"] == "media.details"
    transcodes = [q for _, path, q in plex_online.calls if path == "/photo/:/transcode"]
    assert len(transcodes) == 1 and transcodes[0]["width"] == "300" and transcodes[0]["height"] == "450"
    assert by_title(items, "Inception (2010)")["icon"]["path"] == "icons/base/movie.webp"  # no artwork

    plex_online.calls.clear()
    grid(env, nav.join("grid", "library", fakes.MID, 1))
    assert "/photo/:/transcode" not in plex_online.paths()  # posters come from the cache now


def test_list_rows_reuse_cached_posters(env, plex_online):
    from alfred_plex.views.search import render_search

    before = render_search(make_ctx(env, query="matrix", nav="search")).to_dict()["items"]
    assert by_title(before, "The Matrix (1999)")["icon"]["path"] == "icons/base/movie_bookmarked.webp"
    grid(env, nav.join("grid", "library", fakes.MID, 1))
    after = render_search(make_ctx(env, query="matrix", nav="search")).to_dict()["items"]
    assert by_title(after, "The Matrix (1999)")["icon"]["path"].endswith(".jpg")


def test_grid_details_footer(env, plex_online):
    _, items = grid(env, nav.join("grid", "library", fakes.MID, 1))
    assert by_title(items, "The Matrix (1999)")["subtitle"] == "1999 ǀ 2h 16m"
    assert by_title(items, "Inception (2010)")["subtitle"] == "2010 ǀ 2h 28m"


def test_grid_children_of_a_show(env, plex_online):
    _, items = grid(env, nav.join("grid", "children", fakes.MID, 20))
    assert titles(items) == ["Return", "Dark (2017)", "Dark ǀ Season 1", "Dark ǀ Season 2"]
    assert items[0]["variables"]["nav"] == nav.join("servers", fakes.MID)
    season = items[2]
    assert season["variables"]["action"] == "grid"  # a season opens its episodes
    assert season["subtitle"] == "10 episodes"


def test_grid_search_discover_and_watchlist(env, plex_online, account):
    _, items = grid(env, "grid/search", state=json.dumps({"query": "matrix"}))
    assert {"The Matrix (1999)", "The Matrix OST (1999)"} <= set(titles(items))
    assert items[0]["arg"] == "matrix"  # Return to Plex Search with the query

    account.discover_payload = fakes.discover_search_payload()
    _, items = grid(env, "grid/discover", state=json.dumps({"query": "matrix"}))
    assert titles(items) == ["Return", "The Matrix (1999)", "Dark (2017)", "Keanu Reeves"]
    assert Path(items[1]["icon"]["path"]).read_bytes() == b"DISCOVER-POSTER"
    assert items[1]["variables"]["action"] == "search"
    assert items[1]["mods"]["cmd"]["variables"]["action"] == "open"  # same shortcuts as the Discover list
    assert items[1]["mods"]["shift"]["variables"]["cmd"] == "watchlist"

    _, items = grid(env, nav.join("grid", "watchlist", fakes.ACCOUNT_UUID))
    assert Path(items[1]["icon"]["path"]).read_bytes() == b"WATCHLIST-POSTER"
    assert json.loads(items[1]["mods"]["cmd"]["variables"]["payload"])["add"] is False


def test_unknown_grid_page(env):
    _, items = grid(env, "grid/nope")
    assert titles(items) == ["Return", "Unknown grid page"]


def test_posters_prune(env, tmp_path):
    ctx = make_ctx(env)
    folder = posters.folder(ctx.settings)
    for index in range(5):
        (folder / f"{index}.jpg").write_bytes(b"x")
    posters.prune(ctx.settings, keep=2)
    assert len(list(folder.glob("*.jpg"))) == 2


# ---------------------------------------------------------------- media sheet
def test_media_details_sheet(env, plex_online):
    result = run(env, alfred.run("media.details", mid=fakes.MID, key=10))
    assert result["action"] == "details" and result["details_file"] == result["arg"]
    path = Path(result["details_file"])
    assert path.parent == Path(env["alfred_workflow_cache"]) / "details"
    text = path.read_text()
    poster = text.splitlines()[0]
    assert poster.startswith("![Poster](../posters/") and (path.parent / poster[10:-1]).exists()
    for expected in ("# The Matrix (1999)", "*Welcome to the Real World*", "**Movie** · 2h 16m · R · Warner Bros.",
                     "⭐ Audience 8.5/10 Rotten Tomatoes", "Your rating 8.0/10", "✓ Played", "A hacker learns",
                     "- **Keanu Reeves** as Neo", "| **Directors** | Lana Wachowski |",
                     "| **Writers** | Lilly Wachowski |", "| **Genres** | Action, Science Fiction |",
                     "| **Collections** | Keanu |", "| **IDs** | TMDB 603 |", "### 📄 The Matrix (1999).mkv",
                     "| **Audio** | English (AAC 5.1) |", "| **Subtitles** | French (SRT) |",
                     "| **Path** | `/movies/The Matrix (1999).mkv` |"):
        assert expected in text, expected


def test_media_page_offers_details_and_children_posters(env, plex_online):
    items = page(env, nav.join("media", fakes.MID, 10))
    sheet = by_title(items, "📖 Full details")["variables"]
    # written while the page renders: the Text View opens on top of the page, ⎋ comes back to it
    assert sheet["action"] == "details" and Path(sheet["details_file"]).read_text().startswith("![Poster]")
    show = page(env, nav.join("media", fakes.MID, 20))
    assert by_title(show, "🖼️ Show its content as posters")["variables"]["action"] == "grid"


def test_human_duration_and_escaping():
    assert details.human_duration(8160000) == "2h 16m"
    assert details.human_duration(1500000) == "25 min"
    assert details.human_duration(None) == ""
    assert details._escape("a|b\nc") == "a\\|b c"
