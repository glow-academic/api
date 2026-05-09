"""Soft calls GET — latest status by call_id from soft_calls_mv."""

import json
from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.soft_calls.types import GetSoftCallResponse

MV_NAME = "soft_calls_mv"


async def get_soft_call(
    conn: asyncpg.Connection,
    call_id: UUID,
    *,
    artifact: str | None = None,
    bypass_mv: bool = False,
) -> GetSoftCallResponse | None:
    """Return the latest status row for ``call_id`` (optionally
    constrained to a specific artifact). ``None`` when no ledger row
    exists for the call.

    Reads from ``soft_calls_mv``; pass ``bypass_mv=True`` to fall back
    to the base table when the MV is stale (debug paths).
    """
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    row = await conn.fetchrow(
        f"""
        SELECT soft_call_entry_id, call_id, artifact, operation,
               status, artifact_id, patch, created_at
        FROM {source}
        WHERE call_id = $1
          AND ($2::text IS NULL OR artifact = $2)
        """,
        call_id,
        artifact,
    )

    if row is None:
        return None

    raw_patch = row["patch"]
    patch = json.loads(raw_patch) if isinstance(raw_patch, str) else raw_patch

    return GetSoftCallResponse(
        id=row["soft_call_entry_id"],
        call_id=row["call_id"],
        artifact=row["artifact"],
        operation=row["operation"],
        status=row["status"],
        artifact_id=row["artifact_id"],
        patch=patch,
        created_at=row["created_at"],
    )
