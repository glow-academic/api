"""Test invocation bridge refresh — recompute the materialized view."""

import asyncpg


async def refresh_test_invocation_bridge(conn: asyncpg.Connection) -> None:
    """Refresh test_invocation_bridge_mv concurrently."""
    await conn.execute(
        "REFRESH MATERIALIZED VIEW CONCURRENTLY test_invocation_bridge_mv"
    )
