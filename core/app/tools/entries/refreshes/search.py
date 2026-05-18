"""Refresh search — filtered/paginated query against refreshes_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.refreshes.types import GetRefreshResponse

MV_NAME = "refreshes_mv"


async def search_refreshes(
    conn: asyncpg.Connection,
    operation_keys: list[UUID] | None = None,
    artifact_type: str | None = None,
    target: str | None = None,
    session_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetRefreshResponse]:
    """Search refresh entries from refreshes_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, operation_key, artifact_type, target, session_id, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR operation_key = ANY($1))
          AND ($2::text IS NULL OR artifact_type = $2)
          AND ($3::text IS NULL OR target = $3)
          AND ($4::uuid[] IS NULL OR session_id = ANY($4))
        ORDER BY created_at DESC
        LIMIT $5 OFFSET $6
        """,
        operation_keys,
        artifact_type,
        target,
        session_ids,
        limit,
        offset,
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
