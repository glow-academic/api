"""MCP tool catalog — the superset of (artifact, operation) pairs to register.

Stateless FastMCP registers tools once at startup, so we can't scope to
a specific agent here. This returns every operation dispatchable through
execute_infra_operation — both structured-path ops (with Pydantic item
classes) and kwargs-path ops (get, search, etc.).

Per-caller scoping (agent's tool subset + profile permissions) happens
at call time in register.py.
"""

from __future__ import annotations

from app.registry.operations import INFRA_OPS


def get_mcp_tool_graph() -> list[tuple[str, str]]:
    """Return every (artifact, operation) pair registered in INFRA_OPS."""
    pairs = sorted(pair for pair, entry in INFRA_OPS.items() if entry is not None)
    return pairs
