"""Plex Search and Plex Discover (live Script Filters)."""

from __future__ import annotations

import json

import fakes
from conftest import came_from, make_ctx, stack

from alfred_plex import alfred, nav
from alfred_plex.alfred import Intent
from alfred_plex.views.discover import render_discover
from alfred_plex.views.search import render_search


def search(env, query: str = "", path: str = "search", **variables) -> list[dict]:
    ctx = make_ctx(env, query=query, nav=path, **variables)
    return render_search(ctx).to_dict()["items"]


def by_title(items, title):
    return next(i for i in items if i["title"] == title)


# --------------------------------------------------------------------- search
def test_no_server(env):
    items = search(env, "matrix")
    assert items[1]["title"] == "No plex media server detected"


def test_hub_search_builds_rows_without_extra_requests(env, plex_online):
    items = search(env, "matrix")
    movie = by_title(items, "The Matrix (1999)")
    assert movie["subtitle"] == ("Home Server ǀ movie ǀ 02:16:00 ǀ Studio: Warner Bros. ǀ "
                                 "Director(s): Lana Wachowski, Lilly Wachowski")
    track = by_title(items, "Don Davis ǀ Matrix Theme")
    assert "Album: The Matrix OST" in track["subtitle"]
    album = by_title(items, "The Matrix OST (1999)")
    assert "12 tracks" in album["subtitle"]
    assert by_title(items, "Keanu Reeves")["icon"]["path"] == "icons/base/person.webp"
    # v2 fetched album().tracks() several times per track: now only identity + hub search.
    assert plex_online.paths() == ["/", "/hubs/search"]


def test_no_return_row_while_typing(env, plex_online):
    assert search(env, "matrix")[0]["title"] != "Return"
    assert search(env, "")[0]["title"] == "Return"


def test_default_shortcuts_on_a_movie(env, plex_online, account):
    account.watchlist_items = []
    movie = by_title(search(env, "matrix"), "The Matrix (1999)")
    # ⏎ nested search is not available for movies: ⏎ opens the media actions page
    assert movie["valid"] is True and movie["variables"]["action"] == "browse"
    assert nav.split(movie["variables"]["nav"]) == ["media", fakes.MID, "10"]
    assert came_from(movie["variables"]).arg == "matrix"  # Return comes back to the results
    assert movie["mods"]["fn"]["variables"]["nav"] == movie["variables"]["nav"]
    played = json.loads(movie["mods"]["cmd+shift"]["variables"]["payload"])
    assert played["played"] is True and played["key"] == 10
    assert movie["mods"]["cmd"]["variables"]["action"] == "open"
    assert movie["mods"]["cmd"]["arg"].startswith("https://app.plex.tv/desktop")
    stream = movie["mods"]["alt"]["variables"]
    assert stream["action"] == "run" and stream["cmd"] == "stream"
    assert json.loads(stream["payload"])["key"] == "/library/metadata/10"
    # tmdb id read from the Guid tags: Movie and TV Show Search is called directly
    assert movie["mods"]["ctrl"]["variables"]["action"] == "mtv"
    assert movie["mods"]["ctrl"]["arg"] == "m:603"
    watch = json.loads(movie["mods"]["shift"]["variables"]["payload"])
    assert watch["add"] is True and watch["guid"] == "plex://movie/5d7768"
    assert Intent.from_dict(watch["_then"]).arg == "matrix"  # comes back to the same results
    assert movie["quicklookurl"].endswith("/library/metadata/10/thumb/1?X-Plex-Token=server-token")


def test_watchlisted_media_is_bookmarked(env, plex_online, account):
    movie = by_title(search(env, "matrix"), "The Matrix (1999)")
    assert movie["icon"]["path"] == "icons/base/movie_bookmarked.webp"  # FakeAccount has it
    assert json.loads(movie["mods"]["shift"]["variables"]["payload"])["add"] is False


def test_nested_search_on_album(env, plex_online):
    album = by_title(search(env, "matrix"), "The Matrix OST (1999)")
    assert album["variables"]["action"] == "search"
    assert album["arg"] == "lt=track/af={'album.title=': 'The Matrix OST', 'artist.title=': 'Don Davis'}"


def test_disabled_shortcuts(env, plex_online):
    env = {**env, "short_web": "False", "short_stream": "False", "short_mtvsearch": "False",
           "short_watchlist": "False", "short_nested_search": "False"}
    env = {**env, "short_actions": "False", "short_played": "False"}
    movie = by_title(search(env, "matrix"), "The Matrix (1999)")
    assert "mods" not in movie
    assert movie["variables"]["action"] == "browse"  # ⏎ still opens the actions page


def test_shortcut_on_enter(env, plex_online):
    movie = by_title(search({**env, "short_web": "arg"}, "matrix"), "The Matrix (1999)")
    assert movie["valid"] is True and movie["variables"]["action"] == "open"


def test_filter_search_only_queries_matching_sections(env, plex_online):
    items = search(env, "lt=movie/tl=matrix")
    assert {i["title"] for i in items[:-3]} == {"The Matrix (1999)", "Inception (2010)"}
    assert items[-1]["title"] == "Return"  # while typing, Return is last: ⏎ opens the first result
    grid = items[-3]
    assert grid["title"] == "🖼️ Show as posters" and grid["variables"]["action"] == "grid"
    assert json.loads(grid["variables"]["state"]) == {"query": "lt=movie/tl=matrix"}
    save = items[-2]
    assert save["title"] == "💾 Save this search as a preset"
    assert save["variables"]["action"] == "ask" and save["variables"]["cmd"] == "preset.save"
    assert json.loads(save["variables"]["payload"])["value"] == "lt=movie/tl=matrix"
    sections = [p for p in plex_online.paths() if p.startswith("/library/sections/")]
    assert "/library/sections/2/all" not in sections  # TV section skipped for libtype=movie


def test_watchlist_filter(env, plex_online):
    items = search(env, "lt=movie/tl=a/wa=1")
    assert [i["title"] for i in items[:-3]] == ["The Matrix (1999)"]
    items = search(env, "lt=movie/tl=a/wa=0")
    assert [i["title"] for i in items[:-3]] == ["Inception (2010)"]


def test_invalid_filter(env, plex_online):
    items = search(env, "nope=1")
    assert items[0]["title"] == "Invalid filters: Unknown filter 'nope'"
    assert items[0]["variables"]["nav"] == "help/alias"


def test_unknown_server_filter_gives_no_media(env, plex_online):
    items = search(env, "lt=movie/sv=Other")
    assert items[0]["title"] == "No media found for these filters"


def test_movie_with_two_versions_opens_streams_page(env, plex_online):
    inception = by_title(search(env, "lt=movie/tl=i"), "Inception (2010)")
    stream = inception["mods"]["alt"]["variables"]
    assert stream["action"] == "search"
    assert nav.split(stream["nav"]) == ["search", "streams", fakes.MID, "11"]
    items = search(env, "", stream["nav"], back=stream["back"])
    assert came_from(stream).arg == "lt=movie/tl=i"
    assert items[0]["title"] == "Return"
    assert Intent.from_dict(items[0]["variables"]) is not None
    assert items[0]["arg"] == "lt=movie/tl=i"  # back to the same filters
    first, second = items[1:]
    assert first["title"] == "1080p (HEVC Main 10)"
    assert "English (AAC Stereo)" in first["subtitle"] and "French (SRT)" in first["subtitle"]
    assert json.loads(second["variables"]["payload"])["media"] == 1


def test_guid_page_from_discover(env, plex_online):
    path = nav.join("search", "guid", "movie", "plex://movie/5d7768", "The Matrix (1999)")
    items = search(env, "", path, back=stack(alfred.discover("matrix")))
    assert items[0]["variables"]["action"] == "discover" and items[0]["arg"] == "matrix"
    assert items[1]["title"] == "The Matrix (1999)"
    assert plex_online.paths().count("/library/all") == 1  # one request, not one per section

    missing = nav.join("search", "guid", "movie", "plex://movie/none", "Nope")
    assert search(env, "", missing)[1]["title"] == "'Nope' is not on your servers"


def test_unreachable_server_is_reported(env, saved, monkeypatch):
    from alfred_plex import plex

    def boom(server):
        raise OSError("down")

    monkeypatch.setattr(plex, "connect", boom)
    items = search(env, "matrix")
    assert any("Failed to connect to the plex server Home Server" in i["title"] for i in items)


# ------------------------------------------------------------------- discover
def discover(env, query: str = "") -> list[dict]:
    return render_discover(make_ctx(env, query=query, nav="discover")).to_dict()["items"]


def test_discover_without_account(env):
    assert discover(env, "matrix")[0]["title"] == "No plex account connected"


def test_discover_search(env, plex_online, account):
    account.discover_payload = fakes.discover_search_payload()
    items = discover(env, "matrix")
    assert [i["title"] for i in items] == ["The Matrix (1999)", "Dark (2017)", "Keanu Reeves", "🖼️ Show as posters",
                                           "Return"]
    url, params = account.queries[-1]
    assert url == "https://discover.provider.plex.tv/library/search"
    assert params["searchTypes"] == "movies,tv,people" and params["query"] == "matrix"

    matrix, dark, keanu, _, _ = items
    assert matrix["icon"]["path"] == "icons/base/movie_discover_bookmarked.webp"
    assert matrix["quicklookurl"] == "https://img/1.jpg"
    nested = matrix["variables"]
    assert nested["action"] == "search" and nav.split(nested["nav"])[1] == "guid"
    assert came_from(nested).arg == "matrix"
    assert json.loads(dark["mods"]["shift"]["variables"]["payload"])["add"] is True
    assert dark["mods"]["ctrl"]["variables"]["cmd"] == "mtv"  # no Guid in the payload: resolved later
    assert keanu["variables"]["action"] == "search" and keanu["arg"] == "Keanu Reeves"
    assert "%2Flibrary%2Fpeople%2Fkeanu" in keanu["mods"]["cmd"]["arg"]


def test_discover_type_suffix(env, plex_online, account):
    discover(env, "dark/show")
    assert account.queries[-1][1]["searchTypes"] == "tv"
    discover(env, "AC/DC")
    assert account.queries[-1][1]["query"] == "AC/DC"


def test_discover_home_hub(env, plex_online, account):
    account.discover_payload = {"MediaContainer": {"Metadata": [
        {"type": "show", "title": "Severance", "year": 2022, "guid": "plex://show/sev", "ratingKey": "sev"}]}}
    items = discover(env, "")
    assert [i["title"] for i in items] == ["Return", "🖼️ Show as posters", "Severance (2022)"]
    assert items[1]["variables"]["action"] == "grid"  # trending as posters, right on top
    assert account.queries[-1][0].endswith("/hubs/sections/home/top_watchlisted")


def test_discover_no_result(env, plex_online, account):
    assert discover(env, "zzz")[0]["title"] == "No media found for 'zzz'"
