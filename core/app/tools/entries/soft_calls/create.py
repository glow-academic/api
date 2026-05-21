"""Soft calls CREATE — append a ledger row to soft_calls_entry.

The ledger is INSERT-only. State changes (pending → accepted/rejected)
are recorded as new rows; ``soft_calls_mv`` keeps the latest per
``call_id`` for fast lookups.

Cache layer (write-back + recent-writes index):
  1. Per-call row at ``entry:soft_call:{call_id}`` — ``get_soft_call``
     reads this first.
  2. Sorted set ``entry:soft_call:recent`` scored by created_at ms —
     ``search_soft_calls`` reads this and merges with the MV result so
     just-written rows are visible to list queries before the async MV
     refresh has run. Capped at last ``_RECENT_CAP`` items.

Together: hedged-read for freshness — cache and MV both consulted, cache
wins on conflict by call_id.
"""

import json
from typing import Any
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.soft_calls.types import CreateSoftCallResponse, GetSoftCallResponse

_TTL = 3600  # 1h — outlives MV refresh window; self-heals on next write
_RECENT_CAP = 1000  # bounds memory of the merge-index
_RECENT_KEY = "entry:soft_call:recent"


def _row_key(call_id: UUID) -> str:
    return f"entry:soft_call:{call_id}"


async def create_soft_call(
    conn: asyncpg.Connection,
    redis: Redis,
    *,
    call_id: UUID,
    artifact: str,
    operation: str,
    artifact_id: UUID,
    status: str = "pending",
    patch: dict[str, Any] | None = None,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateSoftCallResponse:
    """Append a soft-call ledger row, write-back the row, index it for merge."""
    if status not in ("pending", "accepted", "rejected"):
        raise ValueError(f"Invalid status: {status!r}")

    patch_json = json.dumps(patch) if patch is not None else None

    row = await conn.fetchrow(
        """
        INSERT INTO soft_calls_entry
            (id, call_id, artifact, operation, status, artifact_id, patch, active, mcp, generated)
        VALUES (COALESCE($1, uuidv7()), $2, $3, $4, $5, $6, $7::jsonb, $8, $9, true)
        RETURNING id, created_at
        """,
        id,
        call_id,
        artifact,
        operation,
        status,
        artifact_id,
        patch_json,
        not soft,
        mcp,
    )

    if row is None:
        raise ValueError("Failed to create soft_calls_entry row")

    entry_id = row["id"]
    created_at = row["created_at"]

    fresh_json = json.dumps(
        GetSoftCallResponse(
            id=entry_id,
            call_id=call_id,
            artifact=artifact,
            operation=operation,
            status=status,
            artifact_id=artifact_id,
            patch=patch,
            created_at=created_at,
        ).model_dump(mode="json")
    )
    score = int(created_at.timestamp() * 1000)  # ms-precision matches MV ORDER BY

    # One pipeline = one round-trip. Reaches past BatchedRedis (which only
    # batches GET/SETEX/EXPIRE) for the ZADD / ZREMRANGEBYRANK primitives.
    async with redis.pipeline(transaction=False) as pipe:
        pipe.setex(_row_key(call_id), _TTL, fresh_json)
        pipe.zadd(_RECENT_KEY, {str(call_id): score})
        pipe.zremrangebyrank(_RECENT_KEY, 0, -_RECENT_CAP - 1)
        pipe.expire(_RECENT_KEY, _TTL)
        await pipe.execute()

    return CreateSoftCallResponse(id=entry_id)
