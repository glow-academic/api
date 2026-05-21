"""Soft calls GET — latest status by call_id from soft_calls_mv.

Cache layer (write-back only): checks a per-row Redis key populated by
``create_soft_call`` on every status write. Cache HOLDS items in active
flux; reads of items that aren't currently being mutated go straight to
the MV (which is fresh enough by then since the MV refresh worker has
caught up). Cache stays small — only active items occupy it.

We do NOT populate the cache on read miss. That would bloat with every
old call_id ever fetched, none of which need the freshness guarantee.
"""

import json
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.soft_calls.types import GetSoftCallResponse

MV_NAME = "soft_calls_mv"


def _row_key(call_id: UUID) -> str:
    return f"entry:soft_call:{call_id}"


async def get_soft_call(
    conn: asyncpg.Connection,
    call_id: UUID,
    redis: Redis,
    *,
    artifact: str | None = None,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> GetSoftCallResponse | None:
    """Return the latest status row for ``call_id`` (optionally
    constrained to a specific artifact). ``None`` when no ledger row
    matches.

    Reads:
      1. Redis write-back cache (per call_id)
      2. ``soft_calls_mv`` (or base table when ``bypass_mv=True``)
    """
    if not bypass_cache:
        raw = await redis.get(_row_key(call_id))
        if raw is not None:
            if isinstance(raw, bytes):
                raw = raw.decode()
            data = json.loads(raw)
            # Apply the optional artifact filter on the cached row — same
            # semantics as the SQL `($2::text IS NULL OR artifact = $2)`.
            if artifact is not None and data.get("artifact") != artifact:
                return None
            return GetSoftCallResponse.model_validate(data)

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
