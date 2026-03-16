"""Entry refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "test_invocation_groups_mv"


async def refresh_test_invocation_groups(conn: asyncpg.Connection) -> None:
    """Refresh test_invocation_groups_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
