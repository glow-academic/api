"""Refresh GET — batch get from refreshes_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.refreshes.types import GetRefreshResponse

MV_NAME = "refreshes_mv"


async def get_refreshes(
    conn: asyncpg.Connection,
    ids: list[UUID],
    bypass_mv: bool = False,
) -> list[GetRefreshResponse]:
    """Get refresh entries by IDs from refreshes_mv."""
    if not ids:
        return []

    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, operation_key, artifact_type, target, session_id, created_at
        FROM {source}
        WHERE id = ANY($1)
        """,
        ids,
    )

    return [
        GetRefreshResponse(
            id=r["id"],
            operation_key=r["operation_key"],
            artifact_type=r["artifact_type"],
            target=r["target"],
            session_id=r["session_id"],
            created_at=r["created_at"],
        )
        for r in rows
    ]
