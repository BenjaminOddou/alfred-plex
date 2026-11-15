"""Browse pages (menu, accounts, servers, presets, help, confirm).

Server pages run on *real* plexapi 4.18 objects parsed from Plex XML
(see ``fakes.FakeSession``): attribute names are checked for real.
"""

from __future__ import annotations

import json

import fakes
from conftest import make_ctx

from alfred_plex import nav
from alfred_plex.views import render_browse


def page(env, path: str = "", **variables) -> list[dict]:
    ctx = make_ctx(env, nav=path, **variables)
    return render_browse(ctx).to_dict()["items"]


def titles(items: list[dict]) -> list[str]:
    return [i["title"] for i in items]


def by_title(items: list[dict], title: str) -> dict:
    return next(i for i in items if i["title"] == title)


# ---------------------------------------------------------------------- menu
def test_menu_without_account_invites_to_sign_in(env):
    items = page(env)
    assert items[0]["title"] == "Sign in with Plex"
    assert items[0]["variables"]["cmd"] == "account.oauth"
    assert items[1]["variables"]["nav"] == "help/start"
    assert "Plex Search" in titles(items)
    assert by_title(items, "Plex Search")["variables"]["action"] == "search"
    assert by_title(items, "Plex Accounts")["subtitle"].startswith("No account yet")


def test_menu_with_account(env, saved):
    items = page(env)
    assert titles(items) == ["Plex Search", "Plex Discover", "Plex Accounts", "Plex Media Servers", "Plex Presets",
                             "Plex Help"]  # Plex Libraries merged into Plex Search (3.3)
    assert "Return" not in titles(items)
    assert by_title(items, "Plex Search")["subtitle"].startswith("Search medias on 1 server, or browse your libraries")
    assert by_title(items, "Plex Media Servers")["subtitle"] == "1 server: Home Server"
    assert by_title(items, "Plex Accounts")["subtitle"] == "neo"


def test_unknown_path_falls_back_to_menu(env, saved):
    assert titles(page(env, "does/not/exist"))[0] == "Plex Search"


# ---------------------------------------------------------------- navigation
def test_return_goes_to_the_real_parent(env, saved):
    path = nav.join("servers", fakes.MID, "settings", "general")
    ctx = make_ctx(env, nav=path)
    from alfred_plex.views import back_to_parent

    item = back_to_parent(ctx, path).to_dict()
    assert item["variables"]["nav"] == nav.join("servers", fakes.MID, "settings")
    assert item["subtitle"].startswith("Back to Menu › Plex Media Servers › Home Server › Settings")
    assert item["mods"]["cmd"]["variables"]["nav"] == ""


def test_section_root_returns_to_menu(env, saved):
    first = page(env, "servers")[0]
    assert first["title"] == "Return" and first["variables"]["nav"] == ""


def test_page_errors_are_shown_not_raised(env, saved, monkeypatch):
    from alfred_plex import plex

    def boom(server):
        raise OSError("connection refused")

    monkeypatch.setattr(plex, "connect", boom)
    items = page(env, nav.join("servers", fakes.MID, "settings"))
    assert items[0]["title"] == "Return"
    assert "Failed to connect to the plex server Home Server" in items[1]["title"]


# ------------------------------------------------------------------ accounts
def test_accounts_root(env, saved):
    items = page(env, "accounts")
    assert titles(items)[1:] == ["Connect a new plex account", "Remove the access to a plex account", "neo"]
    assert by_title(items, "neo")["variables"]["nav"] == nav.join("accounts", fakes.ACCOUNT_UUID)


def test_connect_page_is_oauth_only(env):
    items = page(env, "accounts/new")
    actions = [i for i in items if i["valid"] and i["title"] != "Return"]
    assert [i["variables"]["cmd"] for i in actions] == ["account.oauth"]
    assert all(i["variables"]["action"] != "ask" for i in actions)
    assert page(env, "accounts")[1]["variables"]["cmd"] == "account.oauth"


def test_remove_account_asks_for_confirmation(env, saved):
    item = page(env, "accounts/remove")[1]
    assert item["variables"]["nav"] == "confirm"
    confirm = json.loads(item["variables"]["confirm"])
    assert confirm["yes"]["variables"]["cmd"] == "account.remove"
    # the confirm page renders Yes / Cancel
    items = page(env, "confirm", confirm=item["variables"]["confirm"], back=item["variables"]["back"])
    assert titles(items) == ["Remove neo?", "Yes, continue", "No, cancel"]
    assert items[1]["variables"]["cmd"] == "account.remove"
    assert items[2]["variables"]["nav"] == "accounts/remove"  # cancel = back to where you were


def test_account_devices_sorted_with_cleanup(env, plex_online):
    items = page(env, nav.join("accounts", fakes.ACCOUNT_UUID, "devices"))
    assert titles(items)[:3] == ["Return", "Clean up 1 old device", "Export to CSV"]
    confirm = json.loads(items[1]["variables"]["confirm"])
    assert confirm["subtitle"] == "Old iPad - iOS 12.0"  # never the server, never this workflow
    assert json.loads(confirm["yes"]["variables"]["payload"])["days"] == 90
    rows = items[3:]
    assert [r["title"] for r in rows] == ["iPhone - iOS 18.0", "Old iPad - iOS 12.0", "NAS - Linux 5.10",
                                          "Alfred Plex - macOS 15.1 (current device)"]  # last seen first
    assert rows[0]["subtitle"].startswith("Last seen 2 days ago")
    assert rows[0]["icon"]["path"] == "icons/devices/ios.webp"
    assert rows[-1]["icon"]["path"] == "icons/devices/macos.webp"
    assert rows[0]["mods"]["cmd"]["variables"]["nav"] == "confirm"


def test_device_removal_of_current_device_warns(env, plex_online):
    items = page(env, nav.join("accounts", fakes.ACCOUNT_UUID, "devices", "dev-1"))
    confirm = json.loads(items[1]["variables"]["confirm"])
    assert "account will be disconnected" in confirm["subtitle"]
    assert json.loads(confirm["yes"]["variables"]["payload"])["current"] is True


def test_account_users(env, plex_online):
    items = page(env, nav.join("accounts", fakes.ACCOUNT_UUID, "users"))
    assert json.loads(items[1]["variables"]["payload"])["kind"] == "users"
    assert "trinity has access to 6 libraries" in by_title(items, "trinity")["subtitle"]


def test_account_watchlist_rows(env, plex_online):
    items = page(env, nav.join("accounts", fakes.ACCOUNT_UUID, "watchlist"))
    assert items[1]["variables"]["action"] == "grid"
    item = items[3]
    assert item["title"] == "The Matrix (1999)"
    assert item["variables"]["action"] == "search"
    assert nav.split(item["variables"]["nav"])[:4] == ["search", "guid", "movie", "plex://movie/5d7768"]
    payload = json.loads(item["mods"]["cmd"]["variables"]["payload"])
    assert payload["add"] is False and payload["guid"] == "plex://movie/5d7768"


# ------------------------------------------------------------------- servers
def test_servers_root(env, saved):
    items = page(env, "servers")
    assert titles(items) == ["Return", "Remove the access to a server", "Home Server (neo)"]


def test_no_server(env):
    items = page(env, "servers")
    assert items[1]["title"] == "No plex media server detected"


def test_server_page_owner(env, plex_online):
    items = page(env, nav.join("servers", fakes.MID))
    assert titles(items) == ["Return", "Your server is up to date", "Sessions", "Recently Added", "Continue Watching",
                             "Library Sections", "Statistics", "Settings", "Maintenance", "Activities", "neo"]
    assert by_title(items, "Sessions")["subtitle"].startswith("1 stream playing")
    # a single, non forced, update check (v2 forced two checks against plex.tv)
    assert plex_online.paths().count("/updater/status") == 1
    assert "/updater/check" not in plex_online.paths()


def test_server_page_not_owner(env, plex_online, saved):
    data = json.loads((saved / "servers.json").read_text())
    data["items"][0]["owner"] = False
    (saved / "servers.json").write_text(json.dumps(data))
    assert titles(page(env, nav.join("servers", fakes.MID)))[1:] == ["Shared server", "Recently Added",
                                                                      "Continue Watching", "neo"]


def test_sessions(env, plex_online):
    items = page(env, nav.join("servers", fakes.MID, "sessions"))
    session = items[1]
    assert session["title"] == "The Matrix (1999)"
    assert "Plex for LG - OLED webOS" in session["subtitle"] and "neo" in session["subtitle"]
    terminate = session["mods"]["cmd"]["variables"]
    assert terminate["action"] == "ask" and terminate["cmd"] == "server.terminate"
    assert json.loads(terminate["payload"])["session"] == 42
    assert session["mods"]["alt"]["variables"]["nav"] == nav.join("accounts", fakes.ACCOUNT_UUID, "devices", "tv-1")


def test_settings_groups_and_values(env, plex_online):
    groups = page(env, nav.join("servers", fakes.MID, "settings"))
    assert groups[1]["title"] == "Export to CSV"
    assert groups[2]["title"] == "General" and "2 elements" in groups[2]["subtitle"]
    settings = page(env, nav.join("servers", fakes.MID, "settings", "general"))
    assert titles(settings) == ["Return", "Friendly name", "Verbose logging"]  # hidden one skipped
    ask = settings[1]["variables"]
    assert ask["action"] == "ask" and ask["cmd"] == "server.setting"
    assert json.loads(ask["payload"])["id"] == "FriendlyName"


def test_libraries(env, plex_online):
    items = page(env, nav.join("servers", fakes.MID, "libraries"))
    assert "Scanning: True" in items[1]["subtitle"]  # v2 only said True when *all* sections were scanning
    assert titles(items)[4:] == ["Movies", "TV Shows", "Music"]
    assert items[4]["variables"]["nav"] == nav.join("servers", fakes.MID, "libraries", 1)


def test_history_uses_cached_lookups(env, plex_online):
    items = page(env, nav.join("servers", fakes.MID, "libraries", "history"))[1:]
    assert items[0]["title"] == "Export to CSV"
    assert items[1]["title"] == "The Matrix (1999)"
    assert "Movies" in items[1]["subtitle"] and "neo" in items[1]["subtitle"]
    assert "Living room TV, webOS" in items[1]["subtitle"]
    assert "Deleted Library" in items[2]["subtitle"]
    # accounts and devices are fetched once, not twice per history row as in v2
    assert plex_online.paths().count("/accounts") == 1
    assert plex_online.paths().count("/devices") == 1


# ------------------------------------------------------------------- presets
def test_presets_use_alias_and_flag_unknown_filters(env, saved):
    data = saved / "presets.json"
    data.write_text(json.dumps({"items": [
        {"title": "Good", "subtitle": "", "arg": "libtype=movie/genre=12", "id": "p1"},
        {"title": "Bad", "subtitle": "", "arg": "libtype=movie/bogus=1", "id": "p2"},
    ]}))
    items = page(env, "presets")
    good, bad = by_title(items, "Good"), by_title(items, "Bad")
    assert good["arg"] == "lt=movie/ge=12" and good["variables"]["action"] == "search"
    assert bad["subtitle"].startswith("⚠️ Unknown filter(s): bogus")
    assert good["mods"]["cmd"]["variables"]["nav"] == "presets/p1"
    assert good["mods"]["alt"]["variables"]["nav"] == "confirm"  # delete
    assert good["mods"]["ctrl"]["variables"]["cmd"] == "preset.duplicate"
    assert "shift" not in good["mods"] and bad["mods"]["shift"]["variables"]["cmd"] == "preset.move"
    assert items[-1]["title"] == "Export to CSV"


def test_preset_modify_page(env, saved):
    (saved / "presets.json").write_text(json.dumps({"items": [
        {"title": "Good", "subtitle": "Sub", "arg": "libtype=movie", "id": "p1"}]}))
    items = page(env, "presets/p1")
    assert items[1]["title"] == "Search: Good" and items[1]["arg"] == "lt=movie"
    assert items[2]["variables"]["cmd"] == "preset.edit_title"
    assert items[2]["text"]["copy"] == "Good/Sub"
    assert items[3]["variables"]["cmd"] == "preset.edit_value"
    assert titles(items)[4:] == ["Duplicate", "Move up", "Move down", "Delete"]
    assert items[-1]["variables"]["nav"] == "confirm"


# ---------------------------------------------------------------------- help
def test_help_filters_lists_every_server(env, plex_online):
    items = page(env, "help/filters")
    assert titles(items) == ["Return", "Movies", "TV Shows", "Music"]


def test_help_section_options(env, plex_online):
    items = page(env, nav.join("help", "filters", fakes.MID, 1))
    names = titles(items)
    assert {"Filter Genre", "Filter Unplayed", "Field Title", "Sort Release Date"} <= set(names)
    genre = by_title(items, "Filter Genre")
    assert "Alias: ge" in genre["subtitle"]


def test_help_filter_choices_build_search_queries(env, plex_online):
    items = page(env, nav.join("help", "filters", fakes.MID, 1, "filter", "genre", "string", "Genre"))
    action = by_title(items, "Action")
    assert action["variables"]["action"] == "search"
    assert action["arg"] == "lt=movie/ge=12"
    boolean = page(env, nav.join("help", "filters", fakes.MID, 1, "filter", "unwatched", "boolean", "Unplayed"))
    assert by_title(boolean, "is true")["arg"] == "lt=movie/uw=1"


def test_help_sort_and_field_choices(env, plex_online):
    sorts = page(env, nav.join("help", "filters", fakes.MID, 1, "sort", "titleSort", "none", "Title"))
    assert by_title(sorts, "Descending")["arg"] == "lt=movie/so=titleSort:desc"
    fields = page(env, nav.join("help", "filters", fakes.MID, 1, "field", "year", "integer", "Year"))
    assert by_title(fields, "Year 'is greater than'")["arg"] == "lt=movie/af={'year>>': ''}"


def test_help_alias_rows(env):
    items = page(env, "help/alias")
    reset = by_title(items, "Reset")
    assert reset["variables"]["nav"] == "confirm"
    libtype = by_title(items, "libtype")
    assert libtype["variables"]["cmd"] == "alias.edit" and libtype["match"] == "libtype lt"


def test_help_cache_page(env):
    items = page(env, "help/cache")
    assert items[1]["variables"]["action"] == "reveal"
    assert items[2]["variables"]["nav"] == "confirm"


def test_help_links(env):
    items = page(env, "help/links")
    assert items[1]["variables"]["action"] == "open"
    assert items[1]["icon"]["path"] == "icons/web/github.webp"
