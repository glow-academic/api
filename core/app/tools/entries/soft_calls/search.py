"""Soft calls SEARCH — filtered/paginated query against soft_calls_mv."""

import json
from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.soft_calls.types import GetSoftCallResponse

MV_NAME = "soft_calls_mv"


async def search_soft_calls(
    conn: asyncpg.Connection,
    *,
    artifact: str | None = None,
    artifact_ids: list[UUID] | None = None,
    operation: str | None = None,
    status: str | None = None,
    call_ids: list[UUID] | None = None,
    limit: int = 100,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetSoftCallResponse]:
    """Search ``soft_calls_mv`` with declarative filters.

    Common usages:
      - ``status='pending', operation='delete', artifact='persona'``
        → list of pending soft-deletes (used by search filters to hide
        rows that are dormant pending hard delete).
      - ``artifact_ids=[...]`` → which of these rows have a pending op?
    """
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT soft_call_entry_id, call_id, artifact, operation,
               status, artifact_id, patch, created_at
        FROM {source}
        WHERE ($1::text     IS NULL OR artifact    = $1)
          AND ($2::uuid[]   IS NULL OR artifact_id = ANY($2))
          AND ($3::text     IS NULL OR operation   = $3)
          AND ($4::text     IS NULL OR status      = $4)
          AND ($5::uuid[]   IS NULL OR call_id     = ANY($5))
        ORDER BY created_at DESC
        LIMIT $6 OFFSET $7
        """,
        artifact,
        artifact_ids,
        operation,
        status,
        call_ids,
        limit,
        offset,
    )

    out: list[GetSoftCallResponse] = []
    for r in rows:
        raw_patch = r["patch"]
        patch = json.loads(raw_patch) if isinstance(raw_patch, str) else raw_patch
        out.append(
            GetSoftCallResponse(
                id=r["soft_call_entry_id"],
                call_id=r["call_id"],
                artifact=r["artifact"],
                operation=r["operation"],
                status=r["status"],
                artifact_id=r["artifact_id"],
                patch=patch,
                created_at=r["created_at"],
            )
        )
    return out
