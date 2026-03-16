"""Entry refresh — reusable data-access layer."""

import asyncpg

MV_NAME = "attempt_message_tree_mv"


async def refresh_attempt_message_tree(conn: asyncpg.Connection) -> None:
    """Refresh attempt_message_tree_mv concurrently."""
    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {MV_NAME}")
