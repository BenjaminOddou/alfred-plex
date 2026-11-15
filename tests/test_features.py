"""3.1 features: media actions, server management, statistics, exports, devices, presets, onboarding."""

from __future__ import annotations

import csv
import json
import zipfile
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import fakes
import pytest
from conftest import came_from, make_ctx, stack
from test_commands import run
from test_views import by_title, page, titles

from alfred_plex import alfred, fmt, nav, stats
from alfred_plex.alfred import Intent
from alfred_plex.commands import media as media_commands
from alfred_plex.commands.media import parse_rating
from alfred_plex.settings import Settings, Shortcuts

MEDIA = nav.join("media", fakes.MID, 10)


def read_csv(path: str) -> list[list[str]]:
    with open(path, encoding="utf-8-sig", newline="") as file:
        return list(csv.reader(file))


# ------------------------------------------------------------- media page
def test_media_page_lists_every_action(env, plex_online):
    items = page(env, MEDIA, back=stack(alfred.search("matrix")))
    assert items[0]["title"] == "Return" and items[0]["arg"] == "matrix"  # back to the search results
    header = items[1]
    assert header["title"] == "The Matrix (1999)"
    assert header["quicklookurl"].endswith("thumb/1?X-Plex-Token=server-token")
    names = titles(items)
    for expected in ("▶️ Play with VLC", "🌐 Open in Plex Web", "⭕ Mark as unplayed", "⭐ Rate",
                     "🔖 Remove from watchlist", "🎬 Movie and TV Show Search", "➕ Playlists",
                     "🗂️ Collections", "📄 The Matrix (1999).mkv", "⬇️ Download", "🔄 Refresh metadata",
                     "🔍 Analyze", "ℹ️ Infos", "🗑️ Delete from the server"):
        assert expected in names, expected
    file_row = by_title(items, "📄 The Matrix (1999).mkv")
    assert file_row["subtitle"].startswith("7.45 GB ǀ mkv ǀ 1080p ǀ hevc ǀ aac ǀ 8000 kbps")
    assert file_row["text"]["copy"] == "/movies/The Matrix (1999).mkv"
    assert file_row["variables"]["cmd"] == "clipboard"  # not on this Mac: copy the path
    assert json.loads(file_row["mods"]["cmd"]["variables"]["payload"])["text"].endswith("X-Plex-Token=server-token")
    assert by_title(items, "⭐ Rate")["subtitle"] == "Your rating: 8.0/10"
    played = json.loads(by_title(items, "⭕ Mark as unplayed")["variables"]["payload"])
    assert played["played"] is False
    infos = by_title(items, "ℹ️ Infos")
    assert "Played 1 time" in infos["subtitle"] and "Action, Science Fiction" in infos["subtitle"]
    assert "A hacker learns the truth." in infos["text"]["largetype"]
    delete = json.loads(by_title(items, "🗑️ Delete from the server")["variables"]["confirm"])
    assert delete["yes"]["variables"]["cmd"] == "media.delete"
    assert Intent.from_dict(json.loads(delete["yes"]["variables"]["payload"])["_then"]).arg == "matrix"


def test_media_page_without_back_returns_to_menu(env, plex_online):
    assert page(env, MEDIA)[0]["variables"]["nav"] == ""


def test_playlists_page(env, plex_online):
    items = page(env, nav.join("media", fakes.MID, 10, "playlists"))
    # smart playlists can't be edited; the media is in no playlist: a message, then the others
    assert titles(items) == ["Return", "➕ New playlist", "The Matrix (1999) is in no playlist yet", "Favorites"]
    payload = json.loads(items[3]["variables"]["payload"])
    assert payload["playlist"] == 500 and payload["key"] == "10"
    assert items[1]["variables"]["action"] == "ask"


def test_playlists_of_the_media_come_first(env, plex_online):
    plex_online.routes["/playlists/500/items"] = (
        '<MediaContainer size="2"><Video ratingKey="11" playlistItemID="1"/>'
        '<Video ratingKey="10" playlistItemID="2"/></MediaContainer>')
    plex_online.routes["/playlists"] = fakes.PLAYLISTS.replace('size="2">', 'size="3">\n'
        '<Playlist ratingKey="502" key="/playlists/502/items" type="playlist" title="Another" playlistType="video" '
        'smart="0" leafCount="1"/>')
    plex_online.routes["/playlists/502/items"] = fakes.EMPTY
    items = page(env, nav.join("media", fakes.MID, 10, "playlists"))
    assert titles(items) == ["Return", "➕ New playlist", "✓ Favorites", "Another"]
    member = json.loads(items[2]["variables"]["payload"])
    assert items[2]["variables"]["cmd"] == "media.playlist_remove" and member["playlist"] == 500
    assert items[3]["variables"]["cmd"] == "media.playlist"


def test_remove_from_playlist(env, plex_online, notifications):
    plex_online.routes["/playlists/500/items"] = (
        '<MediaContainer size="2"><Video ratingKey="11" key="/library/metadata/11" type="movie" title="Inception" '
        'playlistItemID="1"/><Video ratingKey="10" key="/library/metadata/10" type="movie" title="The Matrix" '
        'playlistItemID="2"/></MediaContainer>')
    plex_online.routes["/playlists/500/items/2"] = fakes.EMPTY
    run(env, alfred.run("media.playlist_remove", mid=fakes.MID, key=10, title="The Matrix", playlist=500))
    assert ("DELETE", "/playlists/500/items/2", {}) in [(m, p, {}) for m, p, _ in plex_online.calls]
    assert "removed from the playlist Favorites" in notifications[-1]["message"]


def test_collections_page(env, plex_online):
    items = page(env, nav.join("media", fakes.MID, 10, "collections"))
    assert titles(items)[1:] == ["➕ New collection", "✓ Keanu", "Classics"]  # its collections first
    assert json.loads(by_title(items, "✓ Keanu")["variables"]["payload"])["add"] is False
    assert json.loads(by_title(items, "Classics")["variables"]["payload"])["add"] is True


# --------------------------------------------------------- media commands
@pytest.mark.parametrize("text, value", [("8", 8.0), ("7,5", 7.5), ("", None), ("clear", None)])
def test_parse_rating(text, value):
    assert parse_rating(text) == value


def test_parse_rating_out_of_range():
    with pytest.raises(ValueError):
        parse_rating("11")


def test_media_commands_call_plex(env, plex_online, notifications):
    base = {"mid": fakes.MID, "key": 10, "title": "The Matrix"}
    run(env, alfred.run("media.played", played=False, **base))
    assert plex_online.calls[-1][1] == "/:/unscrobble"
    run(env, alfred.run("media.played", played=True, **base))
    assert plex_online.calls[-1][1] == "/:/scrobble"
    run(env, alfred.ask("Rate", "", "media.rate", **base), "9")
    assert plex_online.calls[-1][:2] == ("PUT", "/:/rate") and plex_online.calls[-1][2]["rating"] == "9.0"
    run(env, alfred.run("media.refresh", **base))
    assert plex_online.calls[-1][:2] == ("PUT", "/library/metadata/10/refresh")
    run(env, alfred.run("media.analyze", **base))
    assert plex_online.calls[-1][:2] == ("PUT", "/library/metadata/10/analyze")
    run(env, alfred.run("media.delete", **base))
    assert plex_online.calls[-1][:2] == ("DELETE", "/library/metadata/10")
    assert notifications[-1]["message"] == "The Matrix is deleted from the server"


def test_add_to_playlist_and_collection(env, plex_online):
    base = {"mid": fakes.MID, "key": 10, "title": "The Matrix"}
    run(env, alfred.run("media.playlist", playlist=500, **base))
    method, path, query = plex_online.calls[-1]
    assert (method, path) == ("PUT", "/playlists/500/items")
    assert query["uri"].endswith("/library/metadata/10")
    run(env, alfred.run("media.collection", name="Classics", add=True, **base))
    method, path, query = plex_online.calls[-1]
    tags = [value for name, value in query.items() if name.startswith("collection[")]
    assert method == "PUT" and tags == ["Keanu", "Classics"]  # existing tags are kept


def test_download_reveals_the_file(env, plex_online, monkeypatch, tmp_path):
    saved = []

    def fake_download(self, savepath=None, keep_original_name=False, **_):
        saved.append((savepath, keep_original_name))
        return [str(Path(savepath) / "The Matrix (1999).mkv")]

    from plexapi.video import Movie

    monkeypatch.setattr(Movie, "download", fake_download)
    result = run(env, alfred.run("media.download", mid=fakes.MID, key=10, title="The Matrix"))
    assert saved == [(env["downloads_folder"], True)]
    assert result["action"] == "reveal" and result["arg"].endswith("The Matrix (1999).mkv")


def test_clipboard(env, monkeypatch, notifications):
    copied = []
    monkeypatch.setattr(media_commands.subprocess, "run", lambda cmd, input=None, **_: copied.append((cmd, input)))
    run(env, alfred.run("clipboard", text="/movies/a.mkv", label="File path"))
    assert copied == [(["pbcopy"], b"/movies/a.mkv")]
    assert notifications[-1]["message"] == "File path copied to the clipboard"


# ---------------------------------------------------------------- servers
def test_recent_and_continue_pages_use_media_rows(env, plex_online):
    recent = page(env, nav.join("servers", fakes.MID, "recent"))
    assert titles(recent)[1:] == ["🖼️ Show as posters", "The Matrix (1999)", "Inception (2010)"]
    assert recent[1]["variables"]["action"] == "grid"
    assert came_from(recent[2]["variables"]).variables["nav"] == nav.join("servers", fakes.MID, "recent")
    assert titles(page(env, nav.join("servers", fakes.MID, "continue")))[2:] == ["Inception (2010)"]


def test_sessions_details(env, plex_online):
    session = page(env, nav.join("servers", fakes.MID, "sessions"))[1]
    assert "Direct Play" in session["subtitle"] and "1000 kbps" in session["subtitle"] and "lan" in session["subtitle"]
    assert nav.split(session["variables"]["nav"]) == ["media", fakes.MID, "10"]


def test_maintenance_page(env, plex_online):
    items = page(env, nav.join("servers", fakes.MID, "maintenance"))
    assert titles(items)[1:] == ["Download server logs", "Download databases", "Empty trash", "Clean bundles",
                                 "Optimize database", "Run task: Backup Database"]
    assert items[3]["variables"]["nav"] == "confirm"
    assert json.loads(items[-1]["variables"]["payload"])["task"] == "BackupDatabase"


def test_activities_page(env, plex_online):
    items = page(env, nav.join("servers", fakes.MID, "activities"))
    assert items[1]["title"] == "Scanning Movies" and "████░░░░░░ 42%" in items[1]["subtitle"]


def test_library_section_page(env, plex_online):
    items = page(env, nav.join("servers", fakes.MID, "libraries", 1))
    assert items[1]["title"] == "Movies: 2 movies"
    assert "46.57 GB" in items[1]["subtitle"] and "10 h" in items[1]["subtitle"]
    assert by_title(items, "Search in Movies")["arg"] == "sc=Movies/tl="
    export = by_title(items, "Export to CSV")
    assert json.loads(export["variables"]["payload"]) == {"kind": "library", "mid": fakes.MID, "section": 1}


def test_maintenance_commands(env, plex_online, notifications, monkeypatch):
    base = {"mid": fakes.MID}
    run(env, alfred.run("server.trash", section=1, **base))
    assert plex_online.calls[-1][:2] == ("PUT", "/library/sections/1/emptyTrash")
    run(env, alfred.run("server.analyze", section=1, **base))
    assert plex_online.calls[-1][:2] == ("PUT", "/library/sections/1/analyze")
    run(env, alfred.run("server.bundles", **base))
    assert plex_online.calls[-1][:2] == ("PUT", "/library/clean/bundles")
    run(env, alfred.run("server.optimize", **base))
    assert plex_online.calls[-1][:2] == ("PUT", "/library/optimize")
    run(env, alfred.run("server.butler", task="BackupDatabase", title="Backup Database", **base))
    assert plex_online.calls[-1][:2] == ("POST", "/butler/BackupDatabase")
    run(env, alfred.run("server.install", **base))
    assert "can't install updates by itself" in notifications[-1]["message"]
    run(env, alfred.ask("Terminate all", "", "server.terminate_all", **base), "Bye")
    assert plex_online.calls[-1][2] == {"sessionId": "abc123", "reason": "Bye"}


def test_download_logs_reveals_the_zip(env, plex_online, monkeypatch):
    from plexapi.server import PlexServer

    monkeypatch.setattr(PlexServer, "downloadLogs", lambda self, savepath=None: f"{savepath}/logs.zip")
    result = run(env, alfred.run("server.logs", mid=fakes.MID))
    assert result["action"] == "reveal" and result["arg"] == f"{env['downloads_folder']}/logs.zip"


# ------------------------------------------------------------- statistics
def test_stats_menu(env, plex_online):
    items = page(env, nav.join("servers", fakes.MID, "stats"))
    assert titles(items)[1:] == ["Live", "Libraries", "Plays", "Bandwidth", "Media Quality"]


def test_live_stats(env, plex_online):
    ctx = make_ctx(env, nav=nav.join("servers", fakes.MID, "stats", "live"))
    from alfred_plex.views import render_browse

    feedback = render_browse(ctx).to_dict()
    assert feedback["rerun"] == 1
    cpu = by_title(feedback["items"], "CPU Usage")
    assert cpu["subtitle"] == "Plex ░░░░░░░░░░ 3.0% ǀ System █░░░░░░░░░ 12.5%"


def test_library_stats(env, plex_online):
    items = page(env, nav.join("servers", fakes.MID, "stats", "libraries"))
    assert items[1]["title"] == "Home Server: 130.39 GB"
    assert by_title(items, "TV Shows")["subtitle"].startswith("0 shows, 0 seasons, 0 episodes ǀ 83.82 GB")


def test_plays_stats(env, plex_online):
    items = page(env, nav.join("servers", fakes.MID, "stats", "plays"))
    assert items[1]["title"] == "2 plays in 15 days"
    assert "1 movie" in items[1]["subtitle"] and "1 episode" in items[1]["subtitle"]
    assert by_title(items, "User: neo")["subtitle"] == "██████████ 2 plays (100%)"
    assert "Title: Lost" in titles(items)  # an episode counts for its show


def test_bandwidth_stats(env, plex_online):
    items = page(env, nav.join("servers", fakes.MID, "stats", "bandwidth"))
    assert items[1]["title"] == "5.0 MB in 15 days"
    assert "Local 2.0 MB (40%)" in items[1]["subtitle"]
    days = [i for i in items if i["title"][:4].isdigit()]
    assert len(days) == 2


def test_quality_stats(env, plex_online):
    items = page(env, nav.join("servers", fakes.MID, "stats", "quality"))
    assert {"Movies: 4K", "Movies: 1080p", "Movies: HDR"} <= set(titles(items))


def test_stats_functions():
    names = stats.Lookups(accounts={1: "neo"}, devices={5: "TV"}, platforms={5: "webOS"}, sections={1: "Movies"})
    day = datetime(2024, 11, 11, 21)  # a Monday
    entries = [
        SimpleNamespace(accountID=1, deviceID=5, librarySectionID=1, type="movie", title="Up", year=2009,
                        viewedAt=day),
        SimpleNamespace(accountID=2, deviceID=7, librarySectionID=9, type="episode", title="Pilot",
                        grandparentTitle="Lost", viewedAt=day + timedelta(days=1)),
    ]
    result = stats.plays(entries, names)
    assert result.total == 2
    assert result.users == Counter({"neo": 1, "Unknown user": 1})
    assert result.titles == Counter({"Up (2009)": 1, "Lost": 1})
    assert result.libraries["Deleted Library"] == 1
    assert result.weekdays == Counter({"Monday": 1, "Tuesday": 1})
    assert result.hours[21] == 2
    samples = [SimpleNamespace(bytes=100, lan=True, at=day, accountID=1, deviceID=5),
               SimpleNamespace(bytes=300, lan=False, at=day, accountID=1, deviceID=5)]
    traffic = stats.bandwidth(samples, names)
    assert (traffic.total, traffic.lan, traffic.wan) == (400, 100, 300)
    assert traffic.days[day.date()] == [100, 300]


def test_format_helpers():
    assert fmt.bar(5, 10) == "█████░░░░░"
    assert fmt.bar(1, 0) == "░" * 10
    assert fmt.share(1, 4) == "25%"
    now = datetime(2024, 1, 31)
    assert fmt.ago(now, now) == "today"
    assert fmt.ago(now - timedelta(days=1), now) == "yesterday"
    assert fmt.ago(now - timedelta(days=90), now) == "3 months ago"
    assert fmt.ago(None) == "never"
    assert fmt.hours(36_000_000) == "10 h"


# ----------------------------------------------------------------- exports
def export(env, **payload) -> tuple[dict, list[list[str]]]:
    result = run(env, alfred.run("export", **payload))
    assert result["action"] == "reveal"
    assert Path(result["arg"]).parent == Path(env["downloads_folder"])
    return result, read_csv(result["arg"])


def test_export_library(env, plex_online):
    result, rows = export(env, kind="library", mid=fakes.MID, section=1)
    assert Path(result["arg"]).name.startswith("plex-home-server-library-")
    assert rows[0][:2] == ["title", "show / artist"] and "file" in rows[0]
    titles_ = [r[0] for r in rows[1:]]
    assert titles_ == ["The Matrix", "Inception"]
    assert rows[1][rows[0].index("tmdb")] == "603"


def test_export_history_and_bandwidth(env, plex_online):
    _, rows = export(env, kind="history", mid=fakes.MID)
    assert rows[0][:3] == ["date", "user", "device"]
    assert rows[1][1:5] == ["neo", "Living room TV", "webOS", "Movies"]
    _, rows = export(env, kind="bandwidth", mid=fakes.MID)
    assert len(rows) == 4 and rows[1][3] == "local"


def test_export_account_data(env, plex_online):
    _, rows = export(env, kind="devices", uuid=fakes.ACCOUNT_UUID)
    assert len(rows) == 5 and rows[1][-1] == "yes"  # this workflow
    _, rows = export(env, kind="watchlist", uuid=fakes.ACCOUNT_UUID)
    assert rows[1][:3] == ["The Matrix", "1999", "movie"]
    _, rows = export(env, kind="users", uuid=fakes.ACCOUNT_UUID)
    assert rows[1][0] == "trinity" and rows[1][-1] == "6"


def test_export_server_tables(env, plex_online):
    _, rows = export(env, kind="settings", mid=fakes.MID)
    assert rows[1][:2] == ["FriendlyName", "Friendly name"]
    _, rows = export(env, kind="libraries", mid=fakes.MID)
    assert rows[1][:3] == ["Movies", "movie", "2"]
    _, rows = export(env, kind="quality", mid=fakes.MID)
    assert ["Movies", "HDR", "2"] in rows
    _, rows = export(env, kind="sessions", mid=fakes.MID)
    assert rows[1][0] == "The Matrix (1999)"


def test_export_presets_and_unknown_kind(env, notifications):
    _, rows = export(env, kind="presets")
    assert rows[0] == ["title", "subtitle", "value", "id"] and len(rows) == 4
    result = run(env, alfred.run("export", kind="nope"))
    assert result["action"] == "done" and "Unknown export" in notifications[-1]["message"]


def test_export_logs_archive(env):
    ctx = make_ctx(env)
    (ctx.settings.cache_dir / "plex.log").write_text("hello")
    result = run(env, alfred.run("logs.export"))
    with zipfile.ZipFile(result["arg"]) as archive:
        assert sorted(archive.namelist()) == ["environment.txt", "plex.log"]
        assert "plexapi: 4.18" in archive.read("environment.txt").decode()


# ----------------------------------------------------------------- devices
def test_devices_cleanup_only_removes_old_clients(env, plex_online, account, notifications):
    run(env, alfred.run("devices.cleanup", uuid=fakes.ACCOUNT_UUID, days=90))
    deleted = [d.name for d in account.devices_list if d.deleted]
    assert deleted == ["Old iPad"]  # not the NAS (server), not this workflow (current token)
    assert notifications[-1]["message"] == "1 old device(s) removed"


def test_stale_days_setting(env, plex_online):
    items = page({**env, "days_devices": "1"}, nav.join("accounts", fakes.ACCOUNT_UUID, "devices"))
    assert items[1]["title"] == "Clean up 2 old devices"


# ----------------------------------------------------------------- presets
def test_duplicate_and_move_presets(env):
    ctx = make_ctx(env)
    first, second = ctx.store.presets.items[:2]
    run(env, alfred.run("preset.duplicate", id=second["id"]))
    names = [p["title"] for p in make_ctx(env).store.presets.items]
    assert names[:3] == [first["title"], second["title"], f"{second['title']} (copy)"]
    run(env, alfred.run("preset.move", id=second["id"], offset=-1))
    assert make_ctx(env).store.presets.items[0]["id"] == second["id"]
    run(env, alfred.run("preset.move", id=second["id"], offset=-1))  # already first: stays first
    assert make_ctx(env).store.presets.items[0]["id"] == second["id"]


def test_save_search_as_preset(env):
    result = run(env, alfred.ask("Title", "", "preset.save", then=alfred.search("lt=movie"), value="lt=movie"),
                 "Movies/All my movies")
    assert result["action"] == "search" and result["arg"] == "lt=movie"
    preset = make_ctx(env).store.presets.items[-1]
    assert (preset["title"], preset["subtitle"], preset["arg"]) == ("Movies", "All my movies", "lt=movie")


# -------------------------------------------------------------- onboarding
def test_help_getting_started_and_shortcuts(env):
    start = page(env, "help/start")
    assert start[1]["title"] == "1. Sign in with Plex" and start[1]["variables"]["cmd"] == "account.oauth"
    shortcuts = page({**env, "short_actions": "cmd+alt", "trigger": "px"}, "help/shortcuts")
    names = titles(shortcuts)
    assert "Keyword px: main menu" in names and not any("Plex Search" in n for n in names)
    assert "⌘⌥⏎  Media actions page" in names
    assert "disabled  Download the file" in names


def test_cache_page_offers_logs_export(env):
    ctx = make_ctx(env)
    (ctx.settings.cache_dir / "plex.log").write_text("x")
    items = page(env, "help/cache")
    assert by_title(items, "Export Workflow Logs")["variables"]["cmd"] == "logs.export"


def test_shortcuts_configuration():
    keys = Settings.from_env({"short_played": "alt+shift", "short_download": "False"}).shortcuts
    assert keys.played == "alt+shift" and keys.download == "" and keys.actions == "fn"
    assert {variable for variable, *_ in Shortcuts.FIELDS} >= {"short_actions", "short_played", "short_download"}
    assert alfred.key_label("cmd+shift") == "⌘⇧⏎" and alfred.key_label("arg") == "⏎"
