"""FIX 2 — ``system.group`` ws handler is registered and reachable.

``core/app/ws/system/`` contained BOTH a ``group.py`` module and a ``group/``
package. Python resolves ``from . import group`` to the *package*, so the
module's ``@sio.on("system.group")`` handler was silently shadowed and never
imported. The canonical handler is ``system/group/get.py`` (operation
``group_get`` — the registry-backed read; the rich detail variant is the HTTP
``POST /system/group`` route). The stale, shadowed ``group.py`` (operation
``group``, which has no projection config in ``app.events.group``) was dead
duplicate code and was removed, eliminating the module/package name clash.

This test asserts ``system.group`` is registered/reachable in the sio handler
registry and that it resolves to the canonical ``group_get`` handler.
"""

from __future__ import annotations

import importlib

import app.ws  # noqa: F401  (importing registers every artifact's handlers)
from app.infra.globals import sio


def test_system_group_event_is_registered() -> None:
    assert "system.group" in sio.handlers["/"], (
        "system.group must be registered in the sio handler registry"
    )


def test_system_group_resolves_to_canonical_get_handler() -> None:
    """The registered handler must be the canonical ``group/get.py`` one — not
    the removed stale ``group.py`` module."""
    handler = sio.handlers["/"]["system.group"]
    # The centralized guard wraps with functools.wraps, so __wrapped__ points
    # at the original handler; fall back to the handler itself if unwrapped.
    original = getattr(handler, "__wrapped__", handler)
    assert original.__module__ == "app.ws.system.group.get", (
        f"system.group should resolve to the canonical get.py handler, "
        f"got {original.__module__}.{original.__qualname__}"
    )


def test_stale_system_group_module_is_gone() -> None:
    """``app.ws.system.group`` must be the package (with __path__), not the
    removed stale module."""
    mod = importlib.import_module("app.ws.system.group")
    assert hasattr(mod, "__path__"), (
        "app.ws.system.group must be a package, not the removed stale module"
    )
