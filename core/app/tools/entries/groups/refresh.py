"""Groups refresh — recompute the materialized view."""

import asyncpg  # type: ignore


async def refresh_groups(conn: asyncpg.Connection) -> None:
    """Refresh groups_mv concurrently.

    Must refresh group_names_mv first since groups_mv joins on it.
    """
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY group_names_mv")
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY groups_mv")
