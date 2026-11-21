"""3.3: history (Return goes back where you came from), loading page, prompts, search + libraries."""

from __future__ import annotations

import json
import time

import fakes
from conftest import came_from, make_ctx, stack
from test_commands import run
from test_views import by_title, page, titles

from alfred_plex import alfred, cli, nav, runs, system
from alfred_plex.views.prompt import render_prompt
from alfred_plex.views.search import render_search


def follow(env, item: dict, **extra) -> list[dict]:
    """Action a browse row like Alfred does (its variables become the env of the next page)."""
    variables = {**item["variables"], **extra}
    return page(env, variables["nav"], **{k: v for k, v in variables.items() if k != "nav"})


# ------------------------------------------------------------------- history
def test_return_goes_back_to_the_screen_you_came_from(env, plex_online):
    server = page(env, nav.join("servers", fakes.MID))
    account_row = by_title(server, "neo")
    account = follow(env, account_row)
    back = account[0]
    assert back["title"] == "Return"
    # not the hierarchical parent (Plex Accounts) but the server page the user came from
    assert back["variables"]["nav"] == nav.join("servers", fakes.MID)
    assert "Home Server" in back["subtitle"]
    # and Return again goes back to where the server page itself came from
    again = follow(env, back)
    assert again[0]["variables"]["nav"] == "servers"


def test_return_without_history_uses_the_parent(env, saved):
    items = page(env, nav.join("servers", fakes.MID, "settings"))
    assert items[0]["variables"]["nav"] == nav.join("servers", fakes.MID)
    assert items[0]["mods"]["cmd"]["variables"]["back"] == "[]"  # ⌘⏎ main menu, fresh history


def test_library_picks_replace_the_library_page(env, plex_online):
    search_page = alfred.search()
    library = page(env, nav.join("library", fakes.MID, 1), back=stack(search_page))
    sort_row = by_title(library, "↕️ Sort: Date Added ↓")
    sorts = follow(env, sort_row)
    title = by_title(sorts, "Title")
    # after the pick, Return on the library page goes to Plex Search, not to the sort picker
    assert [h["action"] for h in alfred.parse_history(title["variables"]["back"])] == ["search"]


def test_media_page_return_keeps_the_search_query(env, plex_online):
    results = render_search(make_ctx(env, query="matrix", nav="search")).to_dict()["items"]
    movie = by_title(results, "The Matrix (1999)")
    media = follow(env, movie)
    assert media[0]["variables"]["action"] == "search" and media[0]["arg"] == "matrix"


# -------------------------------------------------------------- loading page
def test_loading_page_while_running(env):
    intent = alfred.run("media.played", title="The Matrix")
    origin = alfred.browse("presets")
    variables = {**intent.as_vars(), "back": stack(origin)}
    ctx = make_ctx(env, **variables)
    runs.write(ctx.settings, variables["run_id"], state="running", started=time.time() - 3)
    from alfred_plex.views import render_browse

    feedback = render_browse(make_ctx(env, **variables)).to_dict()
    assert feedback["rerun"] == 0.5
    assert feedback["items"][0]["title"] == "⏳ Updating the played state: The Matrix…"
    assert feedback["items"][0]["subtitle"].startswith("3s")
    assert feedback["items"][1]["title"] == "Return" and feedback["items"][1]["variables"]["nav"] == "presets"


def test_loading_page_before_the_command_starts(env):
    intent = alfred.run("export", kind="presets")
    items = page(env, "loading", **{k: v for k, v in intent.as_vars().items() if k != "nav"})
    assert items[0]["title"] == "⏳ Exporting to CSV…"


def test_loading_page_becomes_the_origin_page_with_a_banner(env):
    origin = alfred.browse("presets")
    preset_id = make_ctx(env).store.presets.items[1]["id"]
    intent = alfred.run("preset.duplicate", then=origin, id=preset_id)
    alfred.link([alfred.Item("x", intent=intent)], origin, [alfred.browse("").page()])
    result = run(env, intent)  # executes the command: writes the status file
    assert result["nav"] == "presets"
    items = page(env, "loading", **{k: v for k, v in intent.as_vars().items() if k != "nav"})
    assert items[0]["title"] == "Return" and items[0]["variables"]["nav"] == ""  # presets page's own Return
    assert items[1]["title"].startswith("✅ The preset") and "duplicated" in items[1]["title"]
    assert "Add a new preset" in titles(items)


def test_loading_page_when_the_origin_is_another_view(env, saved, monkeypatch):
    from alfred_plex import plex

    monkeypatch.setattr(plex, "connect", lambda s: (_ for _ in ()).throw(OSError("down")))
    intent = alfred.run("server.scan", mid=fakes.MID)
    alfred.link([alfred.Item("x", intent=intent)], alfred.grid("grid/recent/x"), [])
    run(env, intent)
    items = page(env, "loading", **{k: v for k, v in intent.as_vars().items() if k != "nav"})
    assert items[0]["title"].startswith("🚨 Failed to connect")
    assert items[1]["title"] == "Return" and items[1]["variables"]["action"] == "grid"


def test_details_can_be_shown_again_from_the_loading_page(env, plex_online):
    intent = alfred.run("media.details", mid=fakes.MID, key=10)
    alfred.link([alfred.Item("x", intent=intent)], alfred.grid("grid/recent/x"), [])
    run(env, intent)
    items = page(env, "loading", **{k: v for k, v in intent.as_vars().items() if k != "nav"})
    again = by_title(items, "📖 Show the details again")
    assert again["variables"]["action"] == "details"


def test_only_long_commands_and_errors_are_notified(env, monkeypatch, detached):
    monkeypatch.setattr(cli, "LONG_COMMANDS", {"export"})
    preset_id = make_ctx(env).store.presets.items[1]["id"]
    quick = run(env, alfred.run("preset.duplicate", id=preset_id))
    assert quick["notify_title"] == quick["notify_text"] == ""  # shown in Alfred by the loading page instead
    assert detached == []
    long = run(env, alfred.run("export", kind="presets"))
    assert long["notify_title"] == "✅ Success!" and "exported to" in long["notify_text"]
    failed = run(env, alfred.run("does.not.exist"))
    assert failed["notify_title"] == "🚨 Error!" and failed["notify_text"]


def test_notifications_unticked_keep_the_workflow_silent(env, monkeypatch, detached, tmp_path):
    monkeypatch.setattr(cli, "LONG_COMMANDS", {"export"})
    monkeypatch.setattr(system, "SOUNDS", tmp_path)
    (tmp_path / "Submarine.aiff").write_bytes(b"")
    silent = {**env, "notify": "0"}
    for intent in (alfred.run("export", kind="presets"), alfred.run("does.not.exist")):
        output = run(silent, intent)
        assert output["notify_title"] == output["notify_text"] == ""  # Alfred posts nothing
        status = runs.read(make_ctx(silent).settings, intent.variables["run_id"])
        assert status["state"] in {"done", "error"} and status["messages"]  # the loading page still tells it
    assert detached == []  # no sound either
    assert run({**env, "notify": "1"}, alfred.run("export", kind="presets"))["notify_text"]
    assert detached == [["afplay", str(tmp_path / "Submarine.aiff")]]


def test_notification_sums_up_the_command():
    assert system.notification([]) == ("", "")
    title, text = system.notification([("success", "NAS added"), ("warning", "Failed to connect to: Old")])
    assert title == "⚠️ Warning!" and text == "NAS added ǀ Failed to connect to: Old"
    assert system.notification([("warning", "a"), ("error", "b")])[0] == "🚨 Error!"


def test_notification_sound(env, monkeypatch, tmp_path, detached):
    monkeypatch.setattr(system, "SOUNDS", tmp_path)
    (tmp_path / "Submarine.aiff").write_bytes(b"")
    system.play("Submarine")
    system.play("")  # mute
    system.play("default")  # 3.1 "Classic": not a file, no sound
    assert detached == [["afplay", str(tmp_path / "Submarine.aiff")]]


def test_status_file(env):
    intent = alfred.run("alias.reset", then=alfred.browse("help/alias"))
    run(env, intent)
    status = runs.read(make_ctx(env).settings, intent.variables["run_id"])
    assert status["state"] == "done"
    assert status["messages"] == [["success", "The alias file is reset"]]
    assert status["next"]["variables"]["nav"] == "help/alias"


# -------------------------------------------------------------------- prompt
def test_prompt_has_a_confirm_row_and_a_return(env):
    ask = alfred.ask("Preset Title/Subtitle", "Example: My movies/Some description", "preset.save", value="lt=movie")
    origin = alfred.search("lt=movie")
    variables = {**ask.as_vars(), "back": stack(origin)}
    items = render_prompt(make_ctx(env, query="Movies", **variables)).to_dict()["items"]
    confirm, back = items
    assert confirm["title"] == "Preset Title/Subtitle: Movies"
    assert confirm["arg"] == "Movies" and confirm["variables"]["action"] == "run"
    assert confirm["variables"]["cmd"] == "preset.save" and confirm["variables"]["nav"] == "loading"
    assert json.loads(confirm["variables"]["payload"])["value"] == "lt=movie"
    assert came_from(confirm["variables"]).arg == "lt=movie"  # loading page Return: the search
    assert back["title"] == "Return" and back["variables"]["action"] == "search" and back["arg"] == "lt=movie"


def test_empty_prompt(env):
    ask = alfred.ask("Rate", "0 to 10", "media.rate")
    items = render_prompt(make_ctx(env, **ask.as_vars())).to_dict()["items"]
    assert items[0]["title"] == "Rate" and items[0]["subtitle"] == "Type, then ⏎ ǀ 0 to 10"
    assert items[1]["variables"]["nav"] == ""  # no history: the menu


# ------------------------------------------------------- search + libraries
def test_empty_search_lists_libraries_then_medias(env, plex_online):
    items = render_search(make_ctx(env, nav="search")).to_dict()["items"]
    assert titles(items)[:4] == ["Return", "Movies", "TV Shows", "Music"]
    movies = items[1]
    assert movies["variables"]["nav"] == nav.join("library", fakes.MID, 1)
    assert movies["mods"]["cmd"]["variables"]["action"] == "grid"
    assert "The Matrix (1999)" in titles(items)
    assert came_from(movies["variables"]).action == "search"  # Return from the library comes back here


def test_return_is_last_while_typing(env, plex_online):
    items = render_search(make_ctx(env, query="matrix", nav="search")).to_dict()["items"]
    assert items[0]["title"] != "Return" and items[-1]["title"] == "Return"
