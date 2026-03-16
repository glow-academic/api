"""
Per-artifact metadata — kind, section, endpoints, socket events.

Data sources:
- CRUD vs view: server/app/v5/router.py (lines 105-138)
- Socket handlers: server/app/socket/v4/__init__.py
- Per-artifact endpoints: each server/app/v5/main/{artifact}/__init__.py
- Section mapping: derived from ARTIFACT_ROUTES route prefixes
"""

from __future__ import annotations

from enum import Enum


class ArtifactKind(str, Enum):
    crud = "crud"
    view = "view"


class ArtifactMeta:
    __slots__ = ("kind", "section", "endpoints", "socket_events")

    def __init__(
        self,
        kind: ArtifactKind,
        section: str,
        endpoints: frozenset[str],
        socket_events: frozenset[str] = frozenset(),
    ) -> None:
        self.kind = kind
        self.section = section
        self.endpoints = endpoints
        self.socket_events = socket_events

    def __repr__(self) -> str:
        return (
            f"ArtifactMeta(kind={self.kind.value!r}, section={self.section!r}, "
            f"endpoints={sorted(self.endpoints)}, socket_events={sorted(self.socket_events)})"
        )


# Standard endpoint sets
_CRUD_ENDPOINTS = frozenset(
    {"get", "list", "save", "delete", "duplicate", "draft", "docs", "export"}
)
_SOCKET_EVENTS = frozenset({"generate", "complete", "progress", "error"})

# ---------------------------------------------------------------------------
# 17 CRUD artifacts
# ---------------------------------------------------------------------------
_CRUD: dict[str, tuple[str, bool]] = {
    # (section, has_socket)
    "agent": ("intelligence", True),
    "auth": ("system", False),
    "cohort": ("training", True),
    "department": ("system", True),
    "document": ("management", True),
    "eval": ("system", True),
    "field": ("management", True),
    "model": ("intelligence", True),
    "parameter": ("management", True),
    "persona": ("training", True),
    "profile": ("management", True),
    "provider": ("intelligence", True),
    "rubric": ("system", True),
    "scenario": ("training", True),
    "setting": ("settings", True),
    "simulation": ("training", False),
    "tool": ("intelligence", True),
}

# ---------------------------------------------------------------------------
# 18 view artifacts (endpoints derived from each __init__.py)
# ---------------------------------------------------------------------------
_VIEWS: dict[str, tuple[str, frozenset[str]]] = {
    # (section, endpoints)
    # Full panel views
    "dashboard": (
        "analytics",
        frozenset({"get", "refresh", "docs", "export"}),
    ),
    # Analytics views with refresh
    "reports": ("analytics", frozenset({"search", "export", "refresh", "docs"})),
    "leaderboard": ("leaderboard", frozenset({"get", "refresh", "docs", "export"})),
    "activity": (
        "analytics",
        frozenset({"get", "problem", "refresh", "resolve", "docs"}),
    ),
    "pricing": ("analytics", frozenset({"get", "refresh", "docs", "export"})),
    "health": ("health", frozenset({"get", "refresh", "docs"})),
    "benchmark": ("benchmark", frozenset({"get", "refresh", "docs"})),
    # Simple views
    "home": ("home", frozenset({"get", "export"})),
    "practice": ("practice", frozenset({"get", "export"})),
    "attempt": ("home", frozenset({"get", "archive", "certifficate", "docs"})),
    "record": ("analytics", frozenset()),
    "session": ("analytics", frozenset({"get", "docs"})),
    "group": ("analytics", frozenset({"get", "docs"})),
    "test": ("benchmark", frozenset({"get", "archive", "docs"})),
    "invocation": ("benchmark", frozenset({"get", "draft"})),
    # Special
    "chat": ("home", frozenset({"get", "draft", "refresh", "docs"})),
}

# ---------------------------------------------------------------------------
# Combined registry
# ---------------------------------------------------------------------------
ARTIFACTS: dict[str, ArtifactMeta] = {}

for _name, (_section, _has_socket) in _CRUD.items():
    ARTIFACTS[_name] = ArtifactMeta(
        kind=ArtifactKind.crud,
        section=_section,
        endpoints=_CRUD_ENDPOINTS,
        socket_events=_SOCKET_EVENTS if _has_socket else frozenset(),
    )

for _name, (_section, _endpoints) in _VIEWS.items():
    ARTIFACTS[_name] = ArtifactMeta(
        kind=ArtifactKind.view,
        section=_section,
        endpoints=_endpoints,
    )

# Clean up module namespace
del _name, _section, _has_socket, _endpoints, _CRUD, _VIEWS
