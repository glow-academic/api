"""Inventory tests for attempt routes that are still explicit TODO stubs."""

from __future__ import annotations

STUB_ATTEMPT_ROUTES: list[tuple[str, dict[str, object]]] = []


def test_attempt_stub_routes_inventory_is_empty() -> None:
    """Attempt route TODO inventory should shrink to empty as routes are wired."""
    assert STUB_ATTEMPT_ROUTES == []
