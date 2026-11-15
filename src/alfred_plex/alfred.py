"""Tiny Alfred Script Filter toolkit.

Every actionable item carries an :class:`Intent`. The intent becomes Alfred
variables (``action``, ``nav``...) that the workflow diagram routes on:

    Script Filter ─▶ Router {var:action} ─▶ browse / search / discover / ask / run / open / reveal / mtv

All intents write *every* routing variable, so no stale value can leak from a
previous step of the chain.

Navigation history: the ``back`` variable is a JSON *stack* of the pages the
user came from. :func:`link` pushes the current page on every navigation
intent of a page, and "Return" pops it, so Return always goes back to the
screen the user really came from.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

ROUTING_VARS = ("nav", "cmd", "payload", "prompt_title", "prompt_subtitle", "back", "confirm", "state",
                "details_file", "run_id", "loading_label")
NAV_ACTIONS = {"browse", "search", "discover", "grid", "ask", "run"}
MAX_HISTORY = 25


@dataclass
class Intent:
    """What happens when the user actions an item."""

    action: str
    arg: str = ""
    variables: dict[str, str] = field(default_factory=dict)

    def as_vars(self) -> dict[str, str]:
        data = {key: "" for key in ROUTING_VARS}
        data.update(self.variables)
        data["action"] = self.action
        return data

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action, "arg": self.arg, "variables": self.variables}

    def page(self) -> dict[str, Any]:
        """This intent as a history entry (without its own history)."""
        variables = {k: v for k, v in self.variables.items() if k != "back" and v not in ("", None)}
        return {"action": self.action, "arg": self.arg, "variables": variables}

    def same_page(self, other: Intent | None) -> bool:
        return other is not None and self.page() == other.page()

    @classmethod
    def from_dict(cls, data: dict | None) -> Intent | None:
        if not data or not data.get("action"):
            return None
        return cls(data["action"], data.get("arg", ""), dict(data.get("variables") or {}))

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_json(cls, text: str | None) -> Intent | None:
        try:
            return cls.from_dict(json.loads(text)) if text else None
        except (ValueError, TypeError):
            return None


# ---------------------------------------------------------------- intents
def _state(state: dict | None) -> str:
    return json.dumps(state, ensure_ascii=False, separators=(",", ":"), sort_keys=True) if state else ""


def grid(nav: str, state: dict | None = None) -> Intent:
    """Show posters in Alfred's Grid View (``main.py grid``)."""
    return Intent("grid", variables={"nav": nav, "state": _state(state)})


def details(path: str) -> Intent:
    """Show a Markdown file (media sheet) in Alfred's Text View."""
    return Intent("details", arg=path, variables={"details_file": path})


def browse(nav: str = "", state: dict | None = None) -> Intent:
    """Show a page of the browse Script Filter (menu, accounts, servers...)."""
    return Intent("browse", variables={"nav": nav, "state": _state(state)})


def search(query: str = "", nav: str = "search") -> Intent:
    """Open Plex Search, the query is typed in Alfred's search field."""
    return Intent("search", arg=query, variables={"nav": nav})


def discover(query: str = "") -> Intent:
    return Intent("discover", arg=query, variables={"nav": "discover"})


def run(cmd: str, /, then: Intent | None = None, **payload: Any) -> Intent:
    """Run a background command (``main.py run``).

    Alfred stays open meanwhile: the Router also shows the ``loading`` page,
    which follows the command through its status file (``run_id``).
    """
    if then is not None:
        payload["_then"] = then.to_dict()
    return Intent("run", arg=cmd, variables={
        "cmd": cmd, "payload": json.dumps(payload, ensure_ascii=False), "nav": "loading",
        "run_id": uuid.uuid4().hex[:12], "loading_label": loading_label(cmd, payload),
    })


LABELS = {
    "account.oauth": "Waiting for the Plex sign in in your browser",
    "account.sync": "Syncing the account and its servers",
    "account.remove": "Removing the account",
    "device.remove": "Removing the device",
    "devices.cleanup": "Removing the old devices",
    "export": "Exporting to CSV",
    "logs.export": "Exporting the logs",
    "media.details": "Preparing the details",
    "media.download": "Downloading",
    "media.played": "Updating the played state",
    "media.rate": "Saving the rating",
    "media.delete": "Deleting from the server",
    "media.playlist_remove": "Removing from the playlist",
    "posters.purge": "Purging the poster cache",
    "posters.remove": "Removing the poster from the cache",
    "server.logs": "Downloading the server logs",
    "server.databases": "Downloading the databases",
    "stream": "Starting the player",
    "watchlist": "Updating the watchlist",
}


def loading_label(cmd: str, payload: dict) -> str:
    label = LABELS.get(cmd, "Working")
    title = payload.get("title") or payload.get("name")
    return f"{label}: {title}" if title else label


def ask(title: str, subtitle: str, cmd: str, /, then: Intent | None = None, **payload: Any) -> Intent:
    """Prompt the user for text (a page with a Return row), then run ``cmd`` with it."""
    intent = run(cmd, then=then, **payload)
    intent.action = "ask"
    intent.arg = ""
    intent.variables.update(nav="prompt", prompt_title=title, prompt_subtitle=subtitle)
    return intent


def confirm(title: str, subtitle: str, yes: Intent) -> Intent:
    """Show a Yes / Cancel page before a destructive command (Cancel = Return)."""
    data = {"title": title, "subtitle": subtitle, "yes": yes.to_dict()}
    return Intent("browse", variables={"nav": "confirm", "confirm": json.dumps(data, ensure_ascii=False)})


def open_url(url: str) -> Intent:
    return Intent("open", arg=url)


def reveal(path: str) -> Intent:
    return Intent("reveal", arg=path)


def mtv(query: str) -> Intent:
    """Hand a ``m:<tmdb>`` / ``t:<tmdb>`` id to the Movie and TV Show Search workflow."""
    return Intent("mtv", arg=query)


def done() -> Intent:
    return Intent("done")


# ---------------------------------------------------------------- history
def parse_history(text: str | None) -> list[dict]:
    try:
        data = json.loads(text) if text else []
    except (ValueError, TypeError):
        return []
    if isinstance(data, dict):  # 3.2 stored a single intent
        data = [data]
    return [d for d in data if isinstance(d, dict) and d.get("action")][-MAX_HISTORY:]


def history_json(history: list[dict]) -> str:
    return json.dumps(history[-MAX_HISTORY:], ensure_ascii=False, separators=(",", ":"))


def pop(history: list[dict]) -> Intent | None:
    """The page on top of the stack, carrying the rest of the stack."""
    if not history:
        return None
    intent = Intent.from_dict(history[-1])
    if intent is not None:
        intent.variables["back"] = history_json(history[:-1])
    return intent


def _intents(items: list) -> list[Intent]:
    found = []
    for item in items:
        found += [i for i in [item.intent, *(m.intent for m in item.mods.values())] if i is not None]
    return found


def link(items: list, here: Intent | None, history: list[dict]) -> None:
    """Give every navigation intent of a page its way back.

    ``here`` is the page being displayed (None for transient pages such as a
    prompt, a confirmation or the loading page, which never appear in the
    history). Intents that already set ``back`` (Return rows) are left alone.
    """
    stack = (history + [here.page()]) if here is not None else list(history)
    for intent in _intents(items):
        if intent.action == "details" and "back" not in intent.variables:
            # the media sheet: ↩ in the Text View comes back to this page (main.py back)
            intent.variables["back"] = history_json(stack)
            continue
        if intent.action not in NAV_ACTIONS or "back" in intent.variables:
            continue
        intent.variables["back"] = history_json(stack)
        if intent.action in {"run", "ask"}:
            _link_then(intent, here, history, stack)


def _link_then(intent: Intent, here: Intent | None, history: list[dict], stack: list[dict]) -> None:
    """The page shown after a command gets a history too (the page itself keeps its own)."""
    try:
        payload = json.loads(intent.variables.get("payload") or "{}")
    except ValueError:
        return
    then = Intent.from_dict(payload.get("_then"))
    if then is None or "back" in then.variables:
        return
    then.variables["back"] = history_json(history if then.same_page(here) else stack)
    payload["_then"] = then.to_dict()
    intent.variables["payload"] = json.dumps(payload, ensure_ascii=False)


KEY_SYMBOLS = {"arg": "", "cmd": "⌘", "alt": "⌥", "ctrl": "⌃", "shift": "⇧", "fn": "fn "}


def key_label(key: str) -> str:
    """``cmd+shift`` → ``⌘⇧⏎`` (``""`` → ``disabled``)."""
    if not key:
        return "disabled"
    return "".join(KEY_SYMBOLS.get(part, part) for part in key.split("+")) + "⏎"


# ------------------------------------------------------------------ items
@dataclass
class Mod:
    subtitle: str
    intent: Intent | None = None
    icon: str | None = None
    valid: bool = True

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"subtitle": self.subtitle, "valid": self.valid and self.intent is not None}
        if self.intent:
            data["arg"] = self.intent.arg
            data["variables"] = self.intent.as_vars()
        if self.icon:
            data["icon"] = {"path": self.icon}
        return data


@dataclass
class Item:
    title: str
    subtitle: str = ""
    intent: Intent | None = None
    icon: str | None = None
    mods: dict[str, Mod] = field(default_factory=dict)
    text: str | None = None  # ⌘C / ⌘L content
    quicklook: str | None = None
    autocomplete: str | None = None
    match: str | None = None
    key: str | None = None  # used to de-duplicate results (not sent to Alfred)
    action: str | None = None  # Universal Actions text (→ on the row): the title, readable in Alfred's panel
    arrow: str | None = None  # page path the → action runs on (found back from ``action``, see views.last_arrows)

    @property
    def valid(self) -> bool:
        return self.intent is not None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"title": self.title, "subtitle": self.subtitle, "valid": self.valid}
        if self.intent:
            data["arg"] = self.intent.arg
            data["variables"] = self.intent.as_vars()
        if self.icon:
            data["icon"] = {"path": self.icon}
        if self.mods:
            data["mods"] = {key: mod.to_dict() for key, mod in self.mods.items()}
        if self.text:
            data["text"] = {"copy": self.text, "largetype": self.text}
        if self.quicklook:
            data["quicklookurl"] = self.quicklook
        if self.autocomplete is not None:
            data["autocomplete"] = self.autocomplete
        if self.match:
            data["match"] = self.match
        if self.action:
            data["action"] = {"text": self.action}
            # Alfred ignores "action" when "arg" is empty: pages opened with browse / grid don't read it.
            if not data.get("arg") and (self.intent is None or self.intent.action in {"browse", "grid"}):
                data["arg"] = self.action
        return data


def icon(name: str, folder: str = "base") -> str:
    return f"icons/{folder}/{name}.webp"


def message(title: str, subtitle: str = "", intent: Intent | None = None, icon_name: str = "info") -> Item:
    """An informative row (not actionable unless an intent is given)."""
    return Item(title, subtitle, intent=intent, icon=icon(icon_name))


@dataclass
class Feedback:
    items: list[Item] = field(default_factory=list)
    rerun: float | None = None

    def add(self, *items: Item) -> Feedback:
        self.items.extend(items)
        return self

    def extend(self, items) -> Feedback:
        self.items.extend(items)
        return self

    def dedupe(self) -> Feedback:
        seen: set[str] = set()
        unique = []
        for item in self.items:
            key = item.key or f"{item.title}\0{item.subtitle}"
            if key not in seen:
                seen.add(key)
                unique.append(item)
        self.items = unique
        return self

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"skipknowledge": True, "items": [i.to_dict() for i in self.items]}
        if self.rerun:
            data["rerun"] = self.rerun
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


def run_output(intent: Intent | None) -> str:
    """JSON printed by ``main.py run``: Alfred turns it into variables for the dispatcher."""
    intent = intent or done()
    return json.dumps(
        {"alfredworkflow": {"arg": intent.arg, "variables": intent.as_vars()}},
        ensure_ascii=False,
    )
