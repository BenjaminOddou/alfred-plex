"""Settings, Alfred JSON, navigation paths and formatting helpers."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from alfred_plex import alfred, fmt, nav
from alfred_plex.alfred import Feedback, Intent, Item, Mod
from alfred_plex.settings import Settings, parse_literal


# ------------------------------------------------------------------ settings
class TestSettings:
    def test_defaults_when_alfred_gives_nothing(self):
        settings = Settings.from_env({})
        assert settings.limit == 15
        assert settings.use_alias is True
        assert settings.notify is True  # 🔔 Notifications on by default
        assert settings.media_player == "vlc"
        assert settings.default_view == {"sort": "originallyAvailableAt:desc"}
        assert settings.shortcuts.nested_search == "arg"
        assert settings.shortcuts.watchlist == "shift"
        expected = Path("~/Library/Application Support/Alfred/Workflow Data/com.benjamino.plex")
        assert settings.data_dir == expected.expanduser()

    def test_user_configuration(self, env):
        settings = Settings.from_env({**env, "limit_number": "30", "filters_bool": "0", "media_player": "IINA",
                                      "short_web": "alt+shift", "sound": "", "notify": "0"})
        assert settings.limit == 30
        assert settings.notify is False
        assert settings.use_alias is False
        assert settings.media_player == "iina"
        assert settings.shortcuts.web == "alt+shift"
        assert settings.sound == ""  # mute must stay mute
        assert settings.data_dir == Path(env["data_folder"])

    @pytest.mark.parametrize("value", ["False", "false", ""])
    def test_deactivated_shortcut_is_really_disabled(self, value):
        # v2 kept the string "False" which is truthy: the action was still computed.
        assert Settings.from_env({"short_stream": value}).shortcuts.stream == ""

    @pytest.mark.parametrize("raw, limit", [("abc", 15), ("0", 1), ("-4", 1), ("8", 8)])
    def test_invalid_numbers_fall_back(self, raw, limit):
        assert Settings.from_env({"limit_number": raw}).limit == limit

    def test_default_view_is_parsed_safely(self):
        assert Settings.from_env({"default_view": "{'libtype': 'movie'}"}).default_view == {"libtype": "movie"}
        assert Settings.from_env({"default_view": '{"sort": "addedAt:desc"}'}).default_view == {"sort": "addedAt:desc"}
        # v2 used eval(): any code typed in the configuration was executed.
        assert Settings.from_env({"default_view": "__import__('os').system('echo hacked')"}).default_view == {}
        assert Settings.from_env({"default_view": ""}).default_view == {}

    def test_unknown_player_falls_back_to_vlc(self):
        assert Settings.from_env({"media_player": "mpv"}).media_player == "vlc"

    def test_parse_literal_never_runs_code(self):
        assert parse_literal("{'a': 1}") == {"a": 1}
        assert parse_literal('{"a": true}') == {"a": True}
        with pytest.raises(ValueError):
            parse_literal("__import__('os')")


# -------------------------------------------------------------------- alfred
class TestAlfred:
    def test_intent_writes_every_routing_variable(self):
        data = alfred.browse("servers").as_vars()
        assert data["action"] == "browse"
        assert data["nav"] == "servers"
        # stale values from a previous step are always overwritten
        assert data["cmd"] == data["payload"] == data["back"] == data["confirm"] == ""

    def test_run_intent_carries_payload_and_then(self):
        intent = alfred.run("server.scan", then=alfred.browse("servers"), mid="m1")
        payload = json.loads(intent.variables["payload"])
        assert intent.action == "run" and intent.variables["cmd"] == "server.scan"
        assert payload["mid"] == "m1"
        assert Intent.from_dict(payload["_then"]).variables["nav"] == "servers"

    def test_ask_intent_has_prompt(self):
        intent = alfred.ask("Password", "Input your password", "account.password", username="neo")
        data = intent.as_vars()
        assert data["action"] == "ask"
        assert data["prompt_title"] == "Password"
        assert json.loads(data["payload"]) == {"username": "neo"}

    def test_search_intent_puts_query_in_arg(self):
        intent = alfred.search("lt=movie")
        assert intent.arg == "lt=movie" and intent.variables["nav"] == "search"

    def test_confirm_wraps_yes(self):
        intent = alfred.confirm("Sure?", "", alfred.run("x"))
        data = json.loads(intent.variables["confirm"])
        assert intent.variables["nav"] == "confirm"
        assert data["yes"]["action"] == "run"

    def test_run_intent_opens_the_loading_page(self):
        intent = alfred.run("media.played", title="The Matrix")
        assert intent.variables["nav"] == "loading"
        assert len(intent.variables["run_id"]) == 12
        assert intent.variables["loading_label"] == "Updating the played state: The Matrix"
        assert alfred.ask("Title", "", "x").variables["nav"] == "prompt"


class TestHistory:
    def test_link_pushes_the_current_page(self):
        here = alfred.browse("servers")
        rows = [Item("A", intent=alfred.browse("servers/m1")), Item("B", intent=alfred.open_url("u"))]
        alfred.link(rows, here, [alfred.browse("").page()])
        history = alfred.parse_history(rows[0].intent.variables["back"])
        assert [h["variables"].get("nav", "") for h in history] == ["", "servers"]
        assert "back" not in rows[1].intent.variables  # opening a URL has no way back

    def test_pop_returns_to_the_previous_page_with_its_history(self):
        history = [alfred.browse("").page(), alfred.browse("servers").page()]
        intent = alfred.pop(history)
        assert intent.variables["nav"] == "servers"
        assert alfred.parse_history(intent.variables["back"]) == history[:1]
        assert alfred.pop([]) is None

    def test_transient_pages_are_not_pushed(self):
        rows = [Item("Yes", intent=alfred.run("x"))]
        origin = [alfred.browse("servers").page()]
        alfred.link(rows, None, origin)
        assert alfred.parse_history(rows[0].intent.variables["back"]) == origin

    def test_then_page_keeps_its_own_history(self):
        here = alfred.browse("presets")
        rows = [Item("Del", intent=alfred.run("preset.remove", then=here)),
                Item("Other", intent=alfred.run("x", then=alfred.browse("accounts")))]
        menu = [alfred.browse("").page()]
        alfred.link(rows, here, menu)
        same = json.loads(rows[0].intent.variables["payload"])["_then"]
        other = json.loads(rows[1].intent.variables["payload"])["_then"]
        assert alfred.parse_history(same["variables"]["back"]) == menu  # same page: no push
        assert len(alfred.parse_history(other["variables"]["back"])) == 2

    def test_history_is_bounded_and_flat(self):
        history = [alfred.browse(f"p{i}").page() for i in range(40)]
        text = alfred.history_json(history)
        assert len(alfred.parse_history(text)) == alfred.MAX_HISTORY
        assert "\\\\" not in text  # no nested escaping

    def test_item_json(self):
        item = Item("Title", "Sub", intent=alfred.open_url("https://plex.tv"), icon=alfred.icon("web"),
                    mods={"cmd": Mod("Copy", alfred.browse(""))}, text="copy me", quicklook="https://q")
        data = item.to_dict()
        assert data["valid"] is True and data["arg"] == "https://plex.tv"
        assert data["icon"] == {"path": "icons/base/web.webp"}
        assert data["mods"]["cmd"]["variables"]["action"] == "browse"
        assert data["text"] == {"copy": "copy me", "largetype": "copy me"}
        assert data["quicklookurl"] == "https://q"

    def test_item_without_intent_is_not_actionable(self):
        assert Item("Info").to_dict()["valid"] is False
        assert "arg" not in Item("Info").to_dict()

    def test_feedback_dedupe_and_rerun(self):
        feedback = Feedback([Item("A", "1"), Item("A", "1"), Item("A", "2")], rerun=1)
        data = json.loads(feedback.dedupe().to_json())
        assert [i["subtitle"] for i in data["items"]] == ["1", "2"]
        assert data["rerun"] == 1 and data["skipknowledge"] is True

    def test_feedback_uses_alfred_6_keys(self):
        data = Feedback([Item("A")]).to_dict()
        assert data["strictmods"] is True  # an undefined modifier never runs the ⏎ action
        assert data["iconresize"] == "fit"  # 2:3 posters are not stretched in the lists

    def test_run_output_defaults_to_done(self):
        data = json.loads(alfred.run_output(None))
        assert data["alfredworkflow"]["variables"]["action"] == "done"
        assert data["alfredworkflow"]["variables"]["notify_text"] == ""  # no notification

    def test_intent_from_garbage(self):
        assert Intent.from_json("not json") is None
        assert Intent.from_dict({}) is None


# ----------------------------------------------------------------------- nav
class TestNav:
    def test_join_and_split_quote_segments(self):
        path = nav.join("search", "guid", "movie", "plex://movie/5d77", "AC/DC")
        assert path.count("/") == 4
        assert nav.split(path) == ["search", "guid", "movie", "plex://movie/5d77", "AC/DC"]

    def test_parent(self):
        assert nav.parent("servers/m1/settings/general") == "servers/m1/settings"
        assert nav.parent("servers") == ""
        assert nav.parent("") == ""

    def test_router_prefers_literal_segments(self):
        router = nav.Router()

        @router.page("servers/<mid>")
        def server(mid):
            return f"server {mid}"

        @router.page("servers/remove")
        def remove():
            return "remove"

        @router.page("")
        def menu():
            return "menu"

        handler, params = router.resolve("servers/remove")
        assert handler() == "remove"
        handler, params = router.resolve("servers/abc")
        assert handler(**params) == "server abc"
        assert router.resolve("")[0]() == "menu"
        assert router.resolve("unknown/path/deep") is None


# ----------------------------------------------------------------------- fmt
class TestFormat:
    def test_duration(self):
        assert fmt.duration(8160000) == "02:16:00"
        assert fmt.duration(None) == ""

    def test_size(self):
        assert fmt.size(0) == "0 B"
        assert fmt.size(1536) == "1.5 KB"
        assert fmt.size(5 * 1024**4) == "5.0 TB"

    def test_bitrate(self):
        assert fmt.bitrate(0) == "0 bps"
        assert fmt.bitrate(2 * 1024**2) == "16.0 Mbps"

    def test_join_skips_empty_parts(self):
        assert fmt.join("a", None, "", "b") == "a ǀ b"

    def test_plural(self):
        assert fmt.plural(1, "season") == "1 season"
        assert fmt.plural(2, "library", "libraries") == "2 libraries"
        assert fmt.plural(None, "track") == "0 tracks"

    def test_day(self):
        assert fmt.day(datetime(2024, 5, 1), "%d/%m/%Y") == "01/05/2024"
        assert fmt.day(None) == ""
