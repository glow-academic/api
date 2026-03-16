"""department_drafts refresh — recompute the materialized view."""

import asyncpg


async def refresh_department_drafts(conn: asyncpg.Connection) -> None:
    """Refresh department_drafts_mv concurrently."""
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY department_drafts_mv")
