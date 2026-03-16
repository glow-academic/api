"""MCP tool graph — black box that returns which endpoints to expose as MCP tools.

The canonical key is (artifact, operation) which maps to:
  routes/v5/{artifact}/{operation}.py → handler function

This function is the single point of control for MCP tool availability.
Stubbable for tests. Future: DB-driven, per-org, role-scoped.
"""

from __future__ import annotations


def get_mcp_tool_graph() -> list[tuple[str, str]]:
    """Return (artifact, operation) pairs to expose as MCP tools.

    Each pair maps to app.routes.v5.{artifact}.{operation} module.
    The handler function, request model, and metadata are introspected
    at registration time.
    """
    return [
        # Analytics / read-only views
        ("activity", "get"),
        ("benchmark", "get"),
        ("dashboard", "get"),
        ("leaderboard", "get"),
        ("pricing", "get"),
        ("reports", "search"),

        # Core content artifacts — read
        ("attempt", "get"),
        ("group", "get"),
        ("session", "get"),

        # Content artifacts — full CRUD
        ("cohort", "get"),
        ("cohort", "search"),
        ("cohort", "delete"),
        ("cohort", "duplicate"),
        ("cohort", "draft"),

        ("persona", "get"),
        ("persona", "search"),
        ("persona", "delete"),
        ("persona", "duplicate"),
        ("persona", "draft"),

        ("scenario", "get"),
        ("scenario", "search"),
        ("scenario", "delete"),
        ("scenario", "duplicate"),
        ("scenario", "draft"),

        ("simulation", "get"),
        ("simulation", "search"),
        ("simulation", "delete"),
        ("simulation", "duplicate"),
        ("simulation", "draft"),
    ]
