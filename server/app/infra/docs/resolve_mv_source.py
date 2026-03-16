"""Resolve MV table name or inline definition for bypass_mv queries."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info


async def resolve_mv_source(
    conn: asyncpg.Connection,
    mv_name: str,
    bypass_mv: bool,
) -> str:
    """Return MV name for normal queries, or inline definition as subquery for bypass."""
    if not bypass_mv:
        return mv_name
    mv = await get_mv_info(conn, mv_name)
    if mv is None:
        raise ValueError(f"Materialized view {mv_name} not found")
    return f"({mv.definition}) mv"
