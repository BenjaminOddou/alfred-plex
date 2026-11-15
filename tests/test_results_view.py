"""3.1 features: results view (list, list with posters, grid), poster cache, "More details" (→), playlists order."""

from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree

import fakes
import pytest
from conftest import make_ctx, stack
from test_commands import run
from test_posters import grid
from test_views import by_title, page, titles

from alfred_plex import alfred, cli, nav, posters
from alfred_plex.media import MORE_PREFIX
from alfred_plex.settings import Settings
from alfred_plex.views import last_arrows

MORE = nav.join("more", fakes.MID, 10)


def search(env, query: str = "", **variables) -> list[dict]:
    from alfred_plex.views.search import render_search

    return render_search(make_ctx(env, query=query, **{"nav": "search", **variables})).to_dict()["items"]


def discover(env, query: str = "", **variables) -> list[dict]:
    from alfred_plex.views.discover import render_discover

    return render_discover(make_ctx(env, query=query, **{"nav": "discover", **variables})).to_dict()["items"]


# ------------------------------------------------------------ results view
def test_results_view_setting():
    assert Settings.from_env({}).search_view == "list"  # default: a list without images
    assert Settings.from_env({"search_view": "grid"}).grid_view
    assert Settings.from_env({"search_view": "list_posters"}).list_posters
    assert Settings.from_env({"search_view": "nope"}).search_view == "list"


def test_grid_view_searches_while_typing(env, plex_online):
    env = {**env, "search_view": "grid"}
    items = search(env, "matrix")
    # live results while typing (with posters), ⏎ on the first row shows them in the Grid View
    assert items[0]["title"] == "🖼️ Show as posters"
    assert items[0]["variables"]["action"] == "grid"
    assert json.loads(items[0]["variables"]["state"]) == {"query": "matrix"}
    matrix = by_title(items, "The Matrix (1999)")
    assert matrix["icon"]["path"].endswith(".jpg")
    assert titles(items)[-2:] == ["💾 Save this search as a preset", "Return"]


def test_grid_view_empty_search(env, plex_online):
    items = search({**env, "search_view": "grid"})
    assert titles(items)[:3] == ["Return", "🖼️ Default view as posters", "Movies"]
    assert items[1]["variables"]["action"] == "grid"
    assert items[2]["variables"]["action"] == "grid"  # ⏎ a library as posters
    assert items[2]["mods"]["cmd"]["variables"]["action"] == "browse"  # ⌘⏎ as a list
    assert "The Matrix (1999)" in titles(items)  # the default view, like the list


def test_grid_view_discover(env, plex_online, account):
    account.discover_payload = fakes.discover_search_payload()
    items = discover({**env, "search_view": "grid"}, "matrix")
    assert titles(items) == ["🖼️ Show as posters", "The Matrix (1999)", "Dark (2017)", "Keanu Reeves", "Return"]
    assert items[0]["variables"]["action"] == "grid"
    assert Path(items[1]["icon"]["path"]).exists()


def test_discover_list_shows_posters(env, plex_online, account):
    account.discover_payload = fakes.discover_search_payload()
    plain = discover(env, "matrix")
    assert by_title(plain, "The Matrix (1999)")["icon"]["path"] == "icons/base/movie_discover_bookmarked.webp"
    items = discover({**env, "search_view": "list_posters"}, "matrix")
    poster = Path(by_title(items, "The Matrix (1999)")["icon"]["path"])
    assert poster.read_bytes() == b"DISCOVER-POSTER"
    assert poster.parent == Path(env["alfred_workflow_cache"]) / "posters"
    # resized by Plex first, the original image when the resizer fails
    paths = account._session.paths()
    assert paths[:2] == ["/photo", "/1.jpg"]


def test_relative_discover_images_are_made_absolute():
    assert posters.absolute("/library/metadata/1/thumb").startswith("https://metadata-static.plex.tv/")
    assert posters.absolute("//img/a.jpg") == "https://img/a.jpg"
    assert posters.absolute("") == "" and posters.absolute(None) == ""


# --------------------------------------------------------------- posters
def test_poster_cache_page_purge_and_remove(env, plex_online):
    grid(env, nav.join("grid", "library", fakes.MID, 1))
    cache = page(env, "help/cache")
    row = by_title(cache, "🖼️ Posters & avatars")
    assert row["subtitle"].startswith("1 image,") and row["variables"]["nav"] == "help/cache/posters"

    items = page(env, "help/cache/posters")
    assert titles(items)[:3] == ["Return", "🧹 Purge all posters", "Display Posters Folder"]
    matrix = by_title(items, "The Matrix (1999)")
    assert "movie" in matrix["subtitle"] and "Home Server" in matrix["subtitle"]
    assert Path(matrix["icon"]["path"]).exists()
    assert matrix["mods"]["cmd"]["variables"]["action"] == "reveal"
    payload = json.loads(matrix["variables"]["payload"])
    assert matrix["variables"]["cmd"] == "posters.remove"

    run(env, alfred.run("posters.remove", **payload))
    assert not Path(matrix["icon"]["path"]).exists()
    assert posters.read_index(make_ctx(env).settings) == {}
    assert titles(page(env, "help/cache/posters"))[-1] == "No poster in the cache"

    grid(env, nav.join("grid", "library", fakes.MID, 1))
    purge = by_title(page(env, "help/cache/posters"), "🧹 Purge all posters")
    assert purge["variables"]["nav"] == "confirm"
    run(env, alfred.Intent.from_dict(json.loads(purge["variables"]["confirm"])["yes"]))
    assert posters.usage(make_ctx(env).settings) == (0, 0)


def test_remove_never_leaves_the_posters_folder(env):
    settings = make_ctx(env).settings
    secret = settings.cache_dir / "secret.jpg"
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_bytes(b"x")
    assert posters.remove(settings, "../secret.jpg") is False
    assert secret.exists()


def test_media_page_removes_its_poster(env, plex_online):
    items = page(env, nav.join("media", fakes.MID, 10))
    row = by_title(items, "🧹 Remove the cached poster")
    assert row["variables"]["cmd"] == "posters.remove"
    assert Path(row["icon"]["path"]).exists()


# ------------------------------------------------------------ more details
def right_arrow(env, text: str) -> dict:
    output = json.loads(cli.more_output(make_ctx(env), text))["alfredworkflow"]
    return {"arg": output["arg"], **output["variables"]}


def test_right_arrow_opens_the_full_details_by_default(env, plex_online):
    items = search(env, "matrix")
    matrix = by_title(items, "The Matrix (1999)")
    # the text of Alfred's actions panel is readable: the title (+ server)
    assert matrix["action"] == {"text": "The Matrix (1999) · Home Server"}
    assert "action" not in by_title(items, "Keanu Reeves")  # tags have no details

    result = right_arrow(env, matrix["action"]["text"])
    assert result["action"] == "details"
    text = Path(result["details_file"]).read_text()
    assert text.startswith("![Poster]") and "# The Matrix (1999)" in text
    back = alfred.pop(alfred.parse_history(result["back"]))
    assert back.action == "search" and back.arg == "matrix"  # ⎋ / ↩ / Return go back to the results


@pytest.mark.parametrize("setting, action, check", [
    ("more", "browse", lambda r: r["nav"] == MORE),
    ("actions", "browse", lambda r: nav.split(r["nav"]) == ["media", fakes.MID, "10"]),
    ("play", "run", lambda r: r["cmd"] == "stream"),
    ("web", "open", lambda r: r["arg"].startswith("https://app.plex.tv/")),
])
def test_right_arrow_action_is_configurable(env, plex_online, setting, action, check):
    search(env, "matrix")
    result = right_arrow({**env, "right_arrow": setting}, f"{MORE_PREFIX}{MORE}")
    assert result["action"] == action and check(result)


def test_right_arrow_on_discover(env, plex_online, account):
    xml = ('<MediaContainer><Video title="The Matrix" year="1999" summary="A hacker." duration="8160000" '
           'thumb="https://img/1.jpg"><Role tag="Keanu Reeves" role="Neo"/><Director tag="Lana Wachowski"/>'
           '<Genre tag="Action"/><Guid id="tmdb://603"/></Video></MediaContainer>')
    account.discover_payload = fakes.discover_search_payload()
    marker = by_title(discover(env, "matrix"), "The Matrix (1999)")["action"]["text"]
    account.query = lambda url, **_: ElementTree.fromstring(xml)
    result = right_arrow(env, marker)
    assert result["action"] == "details"
    text = Path(result["details_file"]).read_text()
    for expected in ("![Poster](../posters/", "# The Matrix (1999)", "A hacker.", "- **Keanu Reeves** as Neo",
                     "- **Directors:** Lana Wachowski", "- **Genres:** Action", "- **IDs:** TMDB 603"):
        assert expected in text, expected
    assert right_arrow({**env, "right_arrow": "web"}, marker)["action"] == "open"
    assert right_arrow({**env, "right_arrow": "actions"}, marker)["action"] == "browse"  # More details page


def test_right_arrow_still_accepts_the_raw_target(env, plex_online):
    assert right_arrow({**env, "right_arrow": "more"}, f"{MORE_PREFIX}{MORE}")["nav"] == MORE


def test_right_arrow_on_another_text_searches_it(env):
    output = json.loads(cli.more_output(make_ctx(env), "blade runner"))["alfredworkflow"]
    assert output["variables"]["action"] == "search" and output["arg"] == "blade runner"


def test_browse_rows_get_an_arg_for_universal_actions(env, plex_online):
    items = page(env, nav.join("servers", fakes.MID, "recent"))
    matrix = by_title(items, "The Matrix (1999)")
    # ⏎ opens the actions page (browse): Alfred needs a non-empty arg to offer the Universal Actions
    assert matrix["arg"] == matrix["action"]["text"]


def test_more_details_page(env, plex_online):
    items = page(env, MORE, back=stack(alfred.search("matrix")))
    assert items[0]["title"] == "Return" and items[0]["arg"] == "matrix"
    header = items[1]
    assert header["title"] == "The Matrix (1999)" and header["icon"]["path"].endswith(".jpg")
    assert nav.split(header["variables"]["nav"]) == ["media", fakes.MID, "10"]
    names = titles(items)
    summary = next(i for i in items if i["subtitle"].startswith("📝 Summary"))
    assert summary["text"]["largetype"].startswith("A hacker learns")
    keanu = by_title(items, "🎭 Keanu Reeves")
    assert keanu["subtitle"].startswith("as Neo") and keanu["variables"]["action"] == "search"
    assert "actor=Keanu Reeves" in keanu["arg"] or "ac=Keanu Reeves" in keanu["arg"]
    for expected in ("🎬 Lana Wachowski", "📖 Full sheet", "⚙️ All the actions", "🌐 Open in Plex Web"):
        assert expected in names, expected
    assert any(i["title"].startswith("💾 ") for i in items)


def test_discover_more_details_page(env, plex_online, account):
    xml = ('<MediaContainer><Video title="The Matrix" year="1999" guid="plex://movie/5d7768" '
           'summary="A hacker learns the truth." contentRating="R" duration="8160000" thumb="https://img/1.jpg" '
           'audienceRating="8.7"><Genre tag="Action"/><Role tag="Keanu Reeves" role="Neo"/>'
           '<Director tag="Lana Wachowski"/><Guid id="tmdb://603"/></Video></MediaContainer>')
    account.discover_payload = fakes.discover_search_payload()
    rows = discover(env, "matrix")
    account.query = lambda url, **_: ElementTree.fromstring(xml)
    marker = by_title(rows, "The Matrix (1999)")["action"]["text"]
    assert marker == "The Matrix (1999) · Plex Discover"
    path = last_arrows(make_ctx(env))[marker]
    items = page(env, path)
    assert items[1]["title"] == "The Matrix (1999)" and Path(items[1]["icon"]["path"]).exists()
    names = titles(items)
    assert "A hacker learns the truth." in names and "Action" in names
    assert by_title(items, "🎭 Keanu Reeves")["variables"]["action"] == "discover"
    assert by_title(items, "🎬 Movie and TV Show Search")["arg"] == "m:603"
    assert by_title(items, "🔖 Remove from watchlist")["variables"]["cmd"] == "watchlist"

    person = last_arrows(make_ctx(env))[by_title(rows, "Keanu Reeves")["action"]["text"]]
    people = page(env, person)
    assert people[1]["title"] == "Keanu Reeves" and people[1]["variables"]["action"] == "discover"


def test_grid_tiles_offer_more_details(env, plex_online):
    _, items = grid(env, nav.join("grid", "library", fakes.MID, 1))
    tile = by_title(items, "The Matrix (1999)")
    assert tile["action"]["text"] == "The Matrix (1999) · Home Server"
    assert last_arrows(make_ctx(env))[tile["action"]["text"]] == MORE


# ----------------------------------------------------------------- avatars
def test_users_page_shows_avatars_without_download(env, plex_online):
    items = page(env, nav.join("accounts", fakes.ACCOUNT_UUID, "users"))
    neo, trinity = by_title(items, "neo"), by_title(items, "trinity")
    assert Path(trinity["icon"]["path"]).read_bytes() == "\x89PNG-TRINITY".encode()
    assert Path(neo["icon"]["path"]).parent == Path(env["alfred_workflow_cache"]) / "posters"
    assert not trinity["valid"] and "⬇️ Download all avatars" not in titles(items)  # cache only
    # avatars are listed (and purged) with the posters
    cache = page(env, "help/cache/posters")
    assert "user" in by_title(cache, "trinity")["subtitle"]


def test_account_page_and_server_page_show_the_avatar(env, plex_online, saved):
    items = page(env, nav.join("accounts", fakes.ACCOUNT_UUID))
    assert items[1]["title"] == "neo" and Path(items[1]["icon"]["path"]).exists()
    # accounts saved before 3.1 had no avatar link: it is now kept
    assert json.loads((saved / "accounts.json").read_text())["items"][0]["thumb"] == "https://img/neo.png"
    server = page(env, nav.join("servers", fakes.MID))
    assert Path(by_title(server, "neo")["icon"]["path"]).exists()


def test_session_rows_show_the_user_avatar(env, plex_online):
    items = page(env, nav.join("servers", fakes.MID, "sessions"))
    row = next(i for i in items if "neo" in i["subtitle"])
    assert Path(row["icon"]["path"]).read_bytes() == "\x89PNG-NEO".encode()


def test_accounts_page_shows_the_avatar(env, plex_online, saved):
    data = json.loads((saved / "accounts.json").read_text())
    data["items"][0]["thumb"] = "https://img/neo.png"
    (saved / "accounts.json").write_text(json.dumps(data))
    items = page(env, "accounts")
    assert Path(by_title(items, "neo")["icon"]["path"]).exists()


def test_media_sheet_return_goes_back(env, plex_online):
    from conftest import stack

    items = page(env, nav.join("media", fakes.MID, 10), back=stack(alfred.search("matrix")))
    sheet = by_title(items, "📖 Full details")["variables"]
    assert sheet["action"] == "details"
    output = json.loads(cli.back_output(make_ctx(env, **sheet)))["alfredworkflow"]
    assert output["variables"]["action"] == "browse"  # ↩ in the Text View: the media page again
    assert nav.split(output["variables"]["nav"]) == ["media", fakes.MID, "10"]
    assert alfred.pop(alfred.parse_history(output["variables"]["back"])).arg == "matrix"
