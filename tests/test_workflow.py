"""Integrity of the Alfred workflow package (info.plist, icons, files).

Alfred is not available in CI: these tests make sure the diagram and the
Python code agree with each other.
"""

from __future__ import annotations

import os
import plistlib
import re
from collections import Counter

import pytest
from conftest import ROOT, SRC

from alfred_plex import alfred
from alfred_plex.cli import MODES
from alfred_plex.media import CLASSES, MOD_ICONS
from alfred_plex.settings import Shortcuts

PLIST = plistlib.loads((SRC / "info.plist").read_bytes())
OBJECTS = {o["uid"]: o for o in PLIST["objects"]}
CONNECTIONS = PLIST["connections"]


def of_type(kind: str) -> list[dict]:
    return [o for o in PLIST["objects"] if o["type"] == f"alfred.workflow.{kind}"]


def router() -> dict:
    conditionals = of_type("utility.conditional")
    return next(o for o in conditionals if o["config"]["conditions"][0]["inputstring"] == "{var:action}")


def targets(uid: str) -> list[dict]:
    return [OBJECTS[c["destinationuid"]] for c in CONNECTIONS.get(uid, [])]


# --------------------------------------------------------------------- graph
def test_every_connection_points_to_an_object():
    for source, links in CONNECTIONS.items():
        assert source in OBJECTS
        for link in links:
            assert link["destinationuid"] in OBJECTS


def test_every_object_is_placed_and_documented():
    for uid, obj in OBJECTS.items():
        ui = PLIST["uidata"][uid]
        assert {"xpos", "ypos"} <= set(ui)
        assert ui.get("note"), f"{obj['type']} has no note"


def test_objects_do_not_overlap():
    positions = Counter((ui["xpos"], ui["ypos"]) for ui in PLIST["uidata"].values())
    assert max(positions.values()) == 1


def test_small_diagram():
    # v2 had 133 objects and 95 connections
    assert len(OBJECTS) <= 28  # 3.1: + Universal Action "More details" and its script, + Text View ↩ back


def test_self_triggers_exist():
    trigger_ids = {o["config"]["triggerid"] for o in of_type("trigger.external")}
    assert trigger_ids == {"browse", "search", "discover", "grid", "ask", "dispatch"}
    calls = [o["config"] for o in of_type("output.callexternaltrigger") if o["config"]["workflowbundleid"] == "self"]
    assert {c["externaltriggerid"] for c in calls} == trigger_ids
    assert all(c["passvariables"] for c in calls), "navigation state lives in variables"


def test_query_is_passed_only_where_it_is_shown():
    calls = {o["config"]["externaltriggerid"]: o["config"] for o in of_type("output.callexternaltrigger")}
    assert calls["search"]["passinputasargument"] and calls["discover"]["passinputasargument"]
    assert not calls["browse"]["passinputasargument"] and not calls["ask"]["passinputasargument"]
    assert not calls["grid"]["passinputasargument"]
    assert calls["mtvID"]["workflowbundleid"] == "com.mcknight.movies"


def test_router_handles_every_action_of_the_python_code():
    actions = {c["matchstring"] for c in router()["config"]["conditions"]}
    produced = {
        alfred.browse().action, alfred.search().action, alfred.discover().action, alfred.run("x").action,
        alfred.ask("t", "s", "x").action, alfred.open_url("u").action, alfred.reveal("p").action,
        alfred.mtv("m:1").action, alfred.grid("grid/search").action, alfred.details("/x.md").action,
    }
    assert produced == actions
    assert alfred.done().action not in actions  # "done" ends the chain on purpose


def test_router_outputs_are_all_connected():
    conditions = {c["uid"] for c in router()["config"]["conditions"]}
    wired = {c["sourceoutputuid"] for c in CONNECTIONS[router()["uid"]]}
    assert conditions == wired


def test_entry_points_reach_the_router():
    router_uid = router()["uid"]
    for sf in of_type("input.scriptfilter"):
        assert [t["uid"] for t in targets(sf["uid"])] == [router_uid]
    dispatch = next(o for o in of_type("trigger.external") if o["config"]["triggerid"] == "dispatch")
    assert [t["uid"] for t in targets(dispatch["uid"])] == [router_uid]
    (grid,) = of_type("userinterface.grid")
    assert [t["uid"] for t in targets(grid["uid"])] == [router_uid]


def test_grid_view_chain():
    trigger = next(o for o in of_type("trigger.external") if o["config"]["triggerid"] == "grid")
    (script,) = targets(trigger["uid"])
    assert 'main.py grid "$1"' in script["config"]["script"]
    (grid,) = targets(script["uid"])
    assert grid["type"] == "alfred.workflow.userinterface.grid"
    config = grid["config"]
    assert config["inputtype"] == 0  # items come from the script output (JSON)
    assert config["filterable"] and config["fixedorder"] and config["showtitles"]


def test_text_view_reads_the_details_file():
    (text,) = of_type("userinterface.text")
    assert text["config"]["inputtype"] == 2 and text["config"]["inputfile"] == "{var:details_file}"
    assert text["config"]["behaviour"] == 2  # Markdown preview
    assert "details_file" in alfred.ROUTING_VARS


def test_prompt_and_command_chain():
    # the prompt is a Script Filter (with a Return row), it goes back to the Router like any page
    trigger = next(o for o in of_type("trigger.external") if o["config"]["triggerid"] == "ask")
    (prompt,) = targets(trigger["uid"])
    assert prompt["type"] == "alfred.workflow.input.scriptfilter"
    assert 'main.py prompt "$1"' in prompt["config"]["script"]
    assert prompt["config"]["alfredfiltersresults"] is False
    assert [t["uid"] for t in targets(prompt["uid"])] == [router()["uid"]]
    assert not of_type("input.keyword")
    run = next(o for o in of_type("action.script") if 'main.py run "$1"' in o["config"]["script"])
    (then,) = targets(run["uid"])
    assert then["config"]["externaltriggerid"] == "dispatch"
    assert {"prompt_title", "prompt_subtitle", "run_id", "loading_label"} <= set(alfred.ROUTING_VARS)


def test_commands_keep_alfred_open_on_the_loading_page():
    run_output = next(c for c in router()["config"]["conditions"] if c["matchstring"] == "run")
    wired = [OBJECTS[c["destinationuid"]] for c in CONNECTIONS[router()["uid"]]
             if c.get("sourceoutputuid") == run_output["uid"]]
    kinds = sorted(o["type"].split(".")[-1] for o in wired)
    assert kinds == ["callexternaltrigger", "script"]
    loading = next(o for o in wired if o["type"].endswith("callexternaltrigger"))
    assert loading["config"]["externaltriggerid"] == "browse" and loading["config"]["passvariables"]
    assert alfred.run("x").variables["nav"] == "loading"


def test_text_view_is_stacked():
    (text,) = of_type("userinterface.text")
    assert text["config"]["stackview"] is True  # ⎋ goes back to the Alfred page below


def test_alfred_stays_open_when_a_row_is_actioned():
    # "Don't close" on the links to the Router: the Text View stacks on the visible page, so ⎋ comes back to it
    for source in [*of_type("input.scriptfilter"), *of_type("userinterface.grid")]:
        links = [c for c in CONNECTIONS[source["uid"]] if c["destinationuid"] == router()["uid"]]
        assert links and all(c["vitoclose"] for c in links), source["uid"]


def test_text_view_return_goes_back():
    (text,) = of_type("userinterface.text")
    (script,) = targets(text["uid"])
    assert 'main.py back "$1"' in script["config"]["script"]
    (then,) = targets(script["uid"])
    assert then["config"]["externaltriggerid"] == "dispatch"


# ------------------------------------------------------------------- scripts
def scripts() -> list[str]:
    return [o["config"]["script"] for o in PLIST["objects"] if "script" in o["config"]]


def test_scripts_call_main_with_known_modes():
    found = []
    for script in scripts():
        match = re.search(r'python3 main\.py (\w+) "\$1"', script)
        assert match, script
        found.append(match.group(1))
        assert "/opt/homebrew/bin" in script  # Alfred's PATH misses Homebrew
    assert sorted(found) == sorted(MODES)


def test_script_filters_settings():
    filters = {o["config"]["title"]: o["config"] for o in of_type("input.scriptfilter")}
    assert filters["Plex"]["keyword"] == "{var:trigger}"
    assert filters["Plex"]["alfredfiltersresults"] is True  # pages are filtered by Alfred
    assert filters["Plex Search"]["keyword"] == filters["Plex Discover"]["keyword"] == ""  # reached from the menu
    for live in ("Plex Search", "Plex Discover"):
        assert filters[live]["alfredfiltersresults"] is False  # Python searches on each keystroke
        assert filters[live]["queuemode"] == 2  # a new keystroke cancels the previous run


# --------------------------------------------------------- user configuration
def test_user_configuration_matches_settings():
    variables = {c["variable"] for c in PLIST["userconfigurationconfig"]}
    source = (SRC / "alfred_plex" / "settings.py").read_text()
    used = set(re.findall(r'_(?:text|int|bool|shortcut)\(env, "(\w+)"', source)) | {"sound", "default_view"}
    assert used - {"alfred_workflow_cache"} <= variables
    assert {variable for variable, *_ in Shortcuts.FIELDS} <= variables
    assert {"trigger", "days_devices", "grid_columns"} <= variables
    assert not {"kw_search", "kw_discover"} & variables  # plexs / plexd removed in 3.2
    defaults = {c["variable"]: c["config"].get("default") for c in PLIST["userconfigurationconfig"]}
    for variable, _, default, _ in Shortcuts.FIELDS:  # same defaults in Python and in Alfred
        assert (defaults[variable] if defaults[variable] != "False" else "") == default, variable


def test_disabled_shortcut_label():
    for entry in PLIST["userconfigurationconfig"]:
        if entry["variable"].startswith("short_"):
            labels = [label for label, _ in entry["config"]["pairs"]]
            assert "Disabled" in labels and "Desactivated" not in labels
            assert entry["description"]


def test_versions_are_aligned():
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert f'version = "{PLIST["version"]}"' in pyproject


# --------------------------------------------------------------------- files
def test_notificator_is_the_latest_upstream():
    notificator = SRC / "notificator"
    assert os.access(notificator, os.X_OK)
    text = notificator.read_text()
    assert text.startswith("#!/bin/zsh --no-rcs")
    assert "checksum_icon" in text  # rebuilt when the workflow icon changes


def test_bundled_plexapi_version():
    import plexapi

    major, minor = (int(x) for x in plexapi.VERSION.split(".")[:2])
    assert (major, minor) >= (4, 18)
    assert str(SRC / "lib") in plexapi.__file__


ICON_CALL = re.compile(r'(?:icon\(|icon_name=)"([a-z_]+)"')


@pytest.mark.parametrize("path", sorted((SRC / "alfred_plex").rglob("*.py")), ids=lambda p: p.name)
def test_icons_used_in_code_exist(path):
    for name in ICON_CALL.findall(path.read_text()):
        assert (SRC / "icons" / "base" / f"{name}.webp").exists(), name


def test_dynamic_icons_exist():
    base = SRC / "icons" / "base"
    names = {image for _, image in CLASSES.values()} | set(MOD_ICONS.values())
    names |= {"movie_bookmarked", "show_bookmarked", "vlc", "iina", "infuse", "add", "delete"}
    names |= {f"{kind}_discover" for kind in ("movie", "show", "person")}
    names |= {f"{kind}_discover_bookmarked" for kind in ("movie", "show")}
    names |= {"movie", "show", "artist", "photo"}  # library section types
    missing = sorted(n for n in names if not (base / f"{n}.webp").exists())
    assert missing == []
