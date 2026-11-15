"""Navigation paths and a tiny pattern router.

A page is addressed by a path such as ``servers/<machineId>/libraries/2``.
Each segment is URL-quoted, so titles or GUIDs containing ``/`` are safe.
The parent page is simply the path minus its last segment, which gives a
real, predictable "Return" instead of the old ``level - 1`` arithmetic.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import quote, unquote


def join(*segments: object) -> str:
    return "/".join(quote(str(s), safe="") for s in segments if s is not None and str(s) != "")


def split(path: str | None) -> list[str]:
    return [unquote(s) for s in (path or "").split("/") if s]


def parent(path: str | None) -> str:
    parts = (path or "").split("/")
    return "/".join(parts[:-1]) if len(parts) > 1 else ""


@dataclass
class Route:
    pattern: list[str]
    handler: Callable

    @property
    def specificity(self) -> tuple[int, int]:
        literal = sum(not p.startswith("<") for p in self.pattern)
        return (len(self.pattern), literal)

    def match(self, parts: list[str]) -> dict[str, str] | None:
        if len(parts) != len(self.pattern):
            return None
        params = {}
        for expected, actual in zip(self.pattern, parts, strict=True):
            if expected.startswith("<"):
                params[expected.strip("<>")] = actual
            elif expected != actual:
                return None
        return params


class Router:
    """Map path patterns (``servers/<mid>/settings``) to view functions."""

    def __init__(self) -> None:
        self.routes: list[Route] = []

    def page(self, pattern: str) -> Callable:
        def decorator(func: Callable) -> Callable:
            self.routes.append(Route(pattern.split("/") if pattern else [], func))
            # Literal segments win over parameters: "servers/remove" before "servers/<mid>".
            self.routes.sort(key=lambda r: r.specificity, reverse=True)
            return func

        return decorator

    def resolve(self, path: str) -> tuple[Callable, dict[str, str]] | None:
        parts = split(path)
        for route in self.routes:
            params = route.match(parts)
            if params is not None:
                return route.handler, params
        return None
