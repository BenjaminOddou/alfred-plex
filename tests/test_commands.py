"""Background commands (``main.py run``) and the CLI entry point."""

from __future__ import annotations

import json
import subprocess
import sys
from types import SimpleNamespace

import fakes
import pytest
from conftest import ROOT, make_ctx

from alfred_plex import alfred, cli, commands, plex
from alfred_plex.commands import media as media_commands
from alfred_plex.commands.servers import parse_setting


def run(env, intent: alfred.Intent, text: str = "") -> dict:
    """Execute an intent like Alfred does: variables in the env, text as $1."""
    ctx = make_ctx(env, **intent.as_vars())
    output = json.loads(cli.run_command(ctx, text))["alfredworkflow"]
    return {"arg": output["arg"], **output["variables"]}


# ---------------------------------------------------------------- dispatcher
def test_every_command_is_registered():
    names = set(commands.load())
    assert {"account.oauth", "account.sync", "account.remove", "device.remove", "devices.cleanup",
            "server.remove", "server.logs", "server.databases", "server.terminate", "server.terminate_all",
            "server.scan", "server.refresh", "server.analyze", "server.trash", "server.bundles", "server.optimize",
            "server.butler", "server.install", "server.setting", "watchlist", "stream", "mtv", "media.played",
            "media.rate", "media.refresh", "media.analyze", "media.delete", "media.download", "media.playlist",
            "media.playlist_new", "media.collection", "clipboard", "export", "logs.export", "preset.new_value",
            "preset.new_title", "preset.edit_title", "preset.edit_value", "preset.remove", "preset.duplicate",
            "preset.move", "preset.save", "alias.edit", "alias.reset", "folder.clear"} <= names
    # sign in is OAuth only since 3.1
    assert not {"account.username", "account.password", "account.otp", "account.token"} & names


def test_unknown_command_notifies(env, notifications):
    result = run(env, alfred.run("does.not.exist"))
    assert result["action"] == "done"
    assert notifications[-1]["title"] == "🚨 Error!"


def test_then_is_used_when_command_returns_nothing(env):
    result = run(env, alfred.run("alias.reset", then=alfred.browse("help/alias")))
    assert result["action"] == "browse" and result["nav"] == "help/alias"


def test_plex_errors_are_explained(env, saved, monkeypatch, notifications):
    monkeypatch.setattr(plex, "connect", lambda s: (_ for _ in ()).throw(OSError("down")))
    result = run(env, alfred.run("server.scan", mid=fakes.MID))
    assert result["action"] == "done"
    assert notifications[-1]["message"] == "Failed to connect to the plex server Home Server"


# ------------------------------------------------------------------- presets
def test_create_preset_in_two_prompts(env):
    step = run(env, alfred.ask("Preset Value", "", "preset.new_value"), "lt=movie/ge=12")
    assert step["action"] == "ask" and step["prompt_title"] == "Preset Title/Subtitle"
    final = run(env, alfred.Intent(step["action"], variables={k: v for k, v in step.items() if k != "arg"}),
                "Action/Movies with action")
    assert final["nav"] == "presets"
    ctx = make_ctx(env)
    preset = next(p for p in ctx.store.presets.items if p["title"] == "Action")
    assert preset == {**preset, "subtitle": "Movies with action", "arg": "lt=movie/ge=12"}
    assert len(preset["id"]) == 32


def test_edit_and_remove_preset(env, notifications):
    ctx = make_ctx(env)
    preset_id = ctx.store.presets.items[1]["id"]
    run(env, alfred.run("preset.edit_title", id=preset_id), "New title/New sub")
    run(env, alfred.run("preset.edit_value", id=preset_id), "lt=show")
    preset = make_ctx(env).store.presets.get(preset_id)
    assert (preset["title"], preset["subtitle"], preset["arg"]) == ("New title", "New sub", "lt=show")
    run(env, alfred.run("preset.remove", then=alfred.browse("presets/remove"), id=preset_id))
    assert make_ctx(env).store.presets.get(preset_id) is None
    assert notifications[-1]["message"] == "The preset New title is removed"


def test_preset_needs_a_title(env, notifications):
    run(env, alfred.run("preset.new_title", value="lt=movie"), "  ")
    assert notifications[-1]["title"] == "⚠️ Warning!"


# --------------------------------------------------------------------- alias
def test_edit_alias(env):
    run(env, alfred.run("alias.edit", long="libtype"), "type")
    assert make_ctx(env).store.alias.resolve("type") == "libtype"


@pytest.mark.parametrize("text", ["ge", "", "a=b", "a/b"])
def test_edit_alias_refused(env, notifications, text):
    run(env, alfred.run("alias.edit", long="libtype"), text)
    assert notifications[-1]["title"] == "⚠️ Warning!"
    assert make_ctx(env).store.alias.resolve("lt") == "libtype"


def test_clear_data_keeps_presets(env, saved):
    assert make_ctx(env).store.presets.items  # creates presets.json
    run(env, alfred.run("folder.clear", kind="data"))
    names = sorted(p.name for p in saved.iterdir())
    assert names == ["presets.json"]


def test_clear_cache_keeps_notificator_app(env):
    ctx = make_ctx(env)
    app = ctx.settings.cache_dir / "Notificator for Plex.app"
    app.mkdir()
    (ctx.settings.cache_dir / "account-x.pickle").write_bytes(b"x")
    run(env, alfred.run("folder.clear", kind="cache"))
    assert app.exists() and not (ctx.settings.cache_dir / "account-x.pickle").exists()


# ------------------------------------------------------------------- servers
@pytest.mark.parametrize("raw, kind, value", [
    ("true", "bool", True), ("No", "bool", False), ("42", "int", 42), ("1.5", "double", 1.5),
    ("My server", "text", "My server"), ("'quoted'", "text", "quoted"),
])
def test_parse_setting(raw, kind, value):
    assert parse_setting(raw, kind) == value


@pytest.mark.parametrize("raw, kind", [("maybe", "bool"), ("abc", "int"), ("x", "double")])
def test_parse_setting_errors(raw, kind):
    with pytest.raises(ValueError):
        parse_setting(raw, kind)


def test_change_setting(env, plex_online, notifications):
    run(env, alfred.run("server.setting", mid=fakes.MID, id="LogVerbose"), "true")
    assert ("PUT", "/:/prefs", {"LogVerbose": "true"}) in plex_online.calls
    assert notifications[-1]["message"] == "LogVerbose value is now True"


def test_change_setting_with_wrong_type(env, plex_online, notifications):
    run(env, alfred.run("server.setting", mid=fakes.MID, id="LogVerbose"), "maybe")
    assert notifications[-1]["title"] == "🚨 Error!"
    assert all(method == "GET" for method, _, _ in plex_online.calls)


def test_terminate_session_uses_plexapi_stop(env, plex_online, notifications):
    run(env, alfred.ask("Terminate", "", "server.terminate", mid=fakes.MID, session=42, title="The Matrix"),
        "Time to sleep")
    method, path, query = plex_online.calls[-1]
    assert path == "/status/sessions/terminate"
    assert query == {"sessionId": "abc123", "reason": "Time to sleep"}
    assert notifications[-1]["message"] == "The session 'The Matrix' is terminated"


def test_scan_one_section_and_all(env, plex_online):
    run(env, alfred.run("server.refresh", mid=fakes.MID, section=1))
    assert plex_online.calls[-1][:2] == ("GET", "/library/sections/1/refresh")
    plex_online.routes["/library/sections/all/refresh"] = fakes.EMPTY
    run(env, alfred.run("server.refresh", mid=fakes.MID))
    assert plex_online.calls[-1][1] == "/library/sections/all/refresh"


def test_remove_server(env, saved, notifications):
    run(env, alfred.run("server.remove", mid=fakes.MID))
    assert make_ctx(env).store.servers.items == []
    assert notifications[-1]["message"] == "The plex server Home Server (neo) is removed"


# ------------------------------------------------------------------ accounts
@pytest.fixture
def oauth(monkeypatch, account):
    """Fake Plex OAuth: the browser "returns" the account token."""
    from alfred_plex.commands import accounts as account_commands

    state = {"opened": [], "token": fakes.ACCOUNT_TOKEN}

    class FakePinLogin:
        def __init__(self, oauth):
            assert oauth is True
            self.token = None

        def oauthUrl(self):
            return "https://app.plex.tv/auth/#!?code=abcd"

        def run(self, timeout):
            assert timeout == account_commands.OAUTH_TIMEOUT

        def waitForLogin(self):
            self.token = state["token"]
            return bool(self.token)

    import plexapi.myplex

    monkeypatch.setattr(plexapi.myplex, "MyPlexPinLogin", FakePinLogin)
    monkeypatch.setattr(account_commands, "open_in_background", state["opened"].append)
    monkeypatch.setattr(plex, "sign_in", lambda token: account if token == fakes.ACCOUNT_TOKEN else None)
    return state


def test_oauth_first_sign_in_saves_account_and_servers(env, oauth, account, notifications):
    resource = SimpleNamespace(name="NAS", provides="server", clientIdentifier="nas-1", device="Synology",
                               platformVersion="7.2", accessToken="nas-token", owned=True,
                               connect=lambda timeout: SimpleNamespace(_baseurl="https://nas.plex.direct:32400"))
    offline = SimpleNamespace(name="Old", provides="server", clientIdentifier="old-1",
                              connect=lambda timeout: (_ for _ in ()).throw(OSError("offline")))
    player = SimpleNamespace(name="TV", provides="player")
    account.resources_list = [resource, offline, player]

    result = run(env, alfred.run("account.oauth", then=alfred.browse("accounts")))
    assert oauth["opened"] == ["https://app.plex.tv/auth/#!?code=abcd"]
    assert result["action"] == "browse" and result["nav"] == ""  # a new user lands on the menu
    ctx = make_ctx(env)
    assert ctx.store.account(fakes.ACCOUNT_UUID)["authToken"] == fakes.ACCOUNT_TOKEN
    server = ctx.store.server("nas-1")
    assert server["baseURL"] == "https://nas.plex.direct:32400" and server["owner"] is True
    assert ctx.store.server("old-1") is None
    assert any("Server(s): NAS" in n["message"] for n in notifications)
    assert notifications[-1]["message"] == "Failed to connect to: Old"

    again = run(env, alfred.run("account.oauth", then=alfred.browse("accounts")))
    assert again["nav"] == f"accounts/{fakes.ACCOUNT_UUID}"  # already known: its page


def test_oauth_cancelled(env, oauth, notifications):
    oauth["token"] = None
    result = run(env, alfred.run("account.oauth", then=alfred.browse("accounts")))
    assert result["nav"] == "accounts"
    assert notifications[-1]["message"] == "Plex sign in expired or was cancelled"
    assert make_ctx(env).store.accounts.items == []


def test_remove_account_removes_its_servers(env, saved, notifications):
    run(env, alfred.run("account.remove", uuid=fakes.ACCOUNT_UUID))
    ctx = make_ctx(env)
    assert ctx.store.accounts.items == [] and ctx.store.servers.items == []


def test_remove_current_device_disconnects_account(env, plex_online, account):
    run(env, alfred.run("device.remove", uuid=fakes.ACCOUNT_UUID, client_id="dev-1", current=True))
    assert account.devices_list[0].deleted
    assert make_ctx(env).store.accounts.items == []


# --------------------------------------------------------------------- media
def test_watchlist_toggle_updates_cache(env, plex_online, account):
    ctx = make_ctx(env)
    assert ctx.watchlist(fakes.ACCOUNT_UUID) == {"plex://movie/5d7768"}  # fills the cache
    result = run(env, alfred.run("watchlist", then=alfred.search("matrix"), uuid=fakes.ACCOUNT_UUID,
                                 guid="plex://show/dark", title="Dark", add=True))
    assert account.added == ["plex://show/dark"]
    assert result["action"] == "search" and result["arg"] == "matrix"
    account.watchlist_items = []  # the cache must answer, not plex.tv
    assert make_ctx(env).watchlist(fakes.ACCOUNT_UUID) == {"plex://movie/5d7768", "plex://show/dark"}


def test_watchlist_already_in_wanted_state(env, plex_online, account, notifications):
    from plexapi.exceptions import BadRequest

    def already(item):
        raise BadRequest("already on the watchlist")

    account.addToWatchlist = already
    run(env, alfred.run("watchlist", uuid=fakes.ACCOUNT_UUID, guid="plex://movie/5d7768", title="M", add=True))
    assert notifications[-1]["title"] == "✅ Success!"


def test_mtv_resolves_tmdb_id(env, plex_online, account):
    result = run(env, alfred.run("mtv", uuid=fakes.ACCOUNT_UUID, type="movie", key="inception"))
    assert result["action"] == "mtv" and result["arg"] == "m:27205"
    assert account.queries[-1][0] == "https://metadata.provider.plex.tv/library/metadata/inception"


def test_player_commands():
    urls, titles = ["http://s/a?X-Plex-Token=t"], ["Inception (2010)"]
    vlc = media_commands.build_player_command("vlc", "/opt/homebrew/bin/vlc", urls, titles, audio=False)
    assert vlc[:2] == ["/opt/homebrew/bin/vlc", "-I"] and vlc[-3:] == ["--input-title-format", titles[0], urls[0]]
    iina = media_commands.build_player_command("iina", "iina", urls, titles, audio=True)
    assert iina[:2] == ["iina", "--music-mode"] and "--mpv-force-media-title=Inception (2010)" in iina
    infuse = media_commands.build_player_command("infuse", "open", urls, titles, audio=False)
    # the stream URL is encoded (v2 sent it raw: everything after "?" was lost)
    assert infuse == ["open", "infuse://x-callback-url/play?url=http%3A%2F%2Fs%2Fa%3FX-Plex-Token%3Dt"]


def test_stream_starts_player(env, plex_online, monkeypatch):
    started, killed = [], []
    monkeypatch.setattr(media_commands, "which", lambda name: f"/opt/homebrew/bin/{name}")
    monkeypatch.setattr(media_commands.subprocess, "run", lambda cmd, **_: killed.append(cmd))
    monkeypatch.setattr(media_commands.subprocess, "Popen", lambda cmd, **_: started.append(cmd))
    run(env, alfred.run("stream", mid=fakes.MID, key="/library/metadata/11", type="movie", media=1, part=0))
    assert killed == [["pkill", "-x", "VLC"]]
    assert started[0][-1] == f"{fakes.BASE_URL}/library/parts/1110/1/b.mkv?X-Plex-Token={fakes.TOKEN}"
    assert started[0][-2] == "Inception (2010)"


def test_stream_without_player(env, plex_online, monkeypatch, notifications):
    monkeypatch.setattr(media_commands, "which", lambda name: None)
    run(env, alfred.run("stream", mid=fakes.MID, key="/library/metadata/11", type="movie"))
    assert "Can't find the vlc command line tool" in notifications[-1]["message"]


# ----------------------------------------------------------------------- cli
def test_main_entry_point_end_to_end(env):
    """Run main.py like Alfred does (separate process, env variables)."""
    result = subprocess.run([sys.executable, str(ROOT / "src" / "main.py"), "browse"],
                            env={**env, "nav": "help"}, capture_output=True, text=True, check=True)
    items = json.loads(result.stdout)["items"]
    assert [i["title"] for i in items][:3] == ["Return", "Getting Started", "Keyboard Shortcuts"]


def test_main_run_mode_end_to_end(env):
    intent = alfred.run("alias.reset", then=alfred.browse("help/alias"))
    result = subprocess.run([sys.executable, str(ROOT / "src" / "main.py"), "run", "alias.reset"],
                            env={**env, **intent.as_vars()}, capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["alfredworkflow"]["variables"]["nav"] == "help/alias"


def test_unknown_mode(capsys):
    assert cli.main(["nope"]) == 2


def test_version_change_clears_cache_but_keeps_data(env, saved):
    ctx = make_ctx(env)
    (ctx.settings.cache_dir / "account-x.pickle").write_bytes(b"x")
    (ctx.settings.cache_dir / "acc-uuid-1").write_bytes(b"v2 pickle")
    (saved / "config.ini").write_text("[header]\nversion = 2.4.2\n")
    make_ctx({**env, "alfred_workflow_version": "3.1.0"})
    assert not (ctx.settings.cache_dir / "account-x.pickle").exists()
    assert not (ctx.settings.cache_dir / "acc-uuid-1").exists()
    assert not (saved / "config.ini").exists()
    assert (saved / "accounts.json").exists() and (saved / "servers.json").exists()  # v2 deleted them!
    assert (ctx.settings.cache_dir / "version").read_text() == "3.1.0"


def test_plexapi_config(env):
    ctx = make_ctx({**env, "language": "fr"})
    config = (ctx.settings.cache_dir / "plexapi.ini").read_text()
    assert "language = fr" in config and "product = Alfred Workflow" in config
    assert "container_size" not in config  # v2 set it to 15: every list was paginated by 15
