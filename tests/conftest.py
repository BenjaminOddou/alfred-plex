"""Shared fixtures. Tests never touch the network nor the real Alfred folders."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC / "lib"))
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# plexapi reads its config when first imported: point it to a throwaway file.
_CONFIG = Path(tempfile.mkdtemp()) / "plexapi.ini"
_CONFIG.write_text("[plexapi]\nautoreload = false\n")
os.environ["PLEXAPI_CONFIG_PATH"] = str(_CONFIG)
import fakes  # noqa: E402
import plexapi  # noqa: E402,F401 - load the config now, once for the whole session

from alfred_plex import plex, system  # noqa: E402
from alfred_plex.context import Context  # noqa: E402


@pytest.fixture
def env(tmp_path: Path) -> dict:
    return {
        "data_folder": str(tmp_path / "data"),
        "alfred_workflow_cache": str(tmp_path / "cache"),
        "downloads_folder": str(tmp_path / "downloads"),
        "alfred_workflow_version": "3.0.0",
        "filters_bool": "1",
        "limit_number": "15",
        "PATH": os.environ.get("PATH", ""),
    }


@pytest.fixture(autouse=True)
def messages(monkeypatch) -> list[dict]:
    """Every message of the commands (success / warning / failure), even the ones of quick commands."""
    sent: list[dict] = []

    class Recorder(list):
        def append(self, entry) -> None:
            super().append(entry)
            level, text = entry
            sent.append({"title": system.TITLES[level], "message": text})

    monkeypatch.setattr(system, "MESSAGES", Recorder())
    return sent


@pytest.fixture(autouse=True)
def detached(monkeypatch) -> list[list[str]]:
    """Processes started without waiting (sounds): recorded, never run."""
    started: list[list[str]] = []
    monkeypatch.setattr(system, "_detach", started.append)
    return started


def came_from(variables: dict):
    """Page on top of the history stack carried by an item (where Return will go)."""
    from alfred_plex.alfred import Intent, parse_history

    history = parse_history(variables.get("back"))
    return Intent.from_dict(history[-1]) if history else None


def stack(*intents) -> str:
    """``back`` variable for a page opened from ``intents`` (oldest first)."""
    from alfred_plex.alfred import history_json

    return history_json([i.page() for i in intents])


def make_ctx(env: dict, query: str = "", **variables: str) -> Context:
    ctx = Context.create(query=query, env={**env, **variables})
    plex.bootstrap(ctx.settings)
    return ctx


@pytest.fixture
def ctx(env) -> Context:
    return make_ctx(env)


@pytest.fixture
def session() -> fakes.FakeSession:
    return fakes.FakeSession()


@pytest.fixture
def account() -> fakes.FakeAccount:
    return fakes.FakeAccount()


@pytest.fixture
def saved(env) -> Path:
    """accounts.json + servers.json as written by the workflow."""
    data = Path(env["data_folder"])
    data.mkdir(parents=True, exist_ok=True)
    (data / "accounts.json").write_text(json.dumps({"items": [{
        "title": "neo", "subtitle": "Mail: neo@example.com", "authToken": fakes.ACCOUNT_TOKEN,
        "uuid": fakes.ACCOUNT_UUID,
    }]}))
    (data / "servers.json").write_text(json.dumps({"items": [{
        "title": "Home Server (neo)", "subtitle": "Device: NAS ǀ Version: 1.41", "friendlyName": "Home Server",
        "machineIdentifier": fakes.MID, "baseURL": fakes.BASE_URL, "plexToken": fakes.TOKEN,
        "account_uuid": fakes.ACCOUNT_UUID, "owner": True,
    }]}))
    return data


@pytest.fixture
def plex_online(monkeypatch, session, account, saved):
    """Route plexapi to the fake session and plex.tv to the fake account."""
    from plexapi.server import PlexServer

    monkeypatch.setattr(plex, "connect", lambda s: PlexServer(s["baseURL"], s["plexToken"], session=session))
    monkeypatch.setattr(plex, "load_account", lambda settings, token, uuid, fresh=False: account)
    from alfred_plex import posters

    monkeypatch.setattr(posters, "web_session", lambda: account._session)  # plex.tv avatars
    return session
