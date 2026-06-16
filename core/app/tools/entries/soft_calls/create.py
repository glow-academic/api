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

from app.tools.entries.soft_calls.types import (
    CreateSoftCallResponse,
    GetSoftCallResponse,
)
from app.utils.cache.hedged_row import write_back_row

# Cache namespace shared with get.py/search.py: the per-row key is
# ``entry:soft_call:{call_id}`` and the recent-writes index is
# ``entry:soft_call:recent`` — exactly ``write_back_row``'s
# ``entry:<ENTRY>:<id>`` / ``entry:<ENTRY>:recent`` shape with ENTRY="soft_call"
# and id=call_id. Routing through ``write_back_row`` makes these write-backs
# participate in the report-19 HC2 / report-20 V2 deferral so a SETEX issued
# inside a ``transaction_with_writeback`` fires only on COMMIT (a rollback
# leaves no phantom terminal cache row served for the TTL).
_ENTRY = "soft_call"


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
    eval: bool | None = None,
) -> CreateSoftCallResponse:
    """Append a soft-call ledger row, write-back the row, index it for merge.

    ``eval`` flags the ledger entry as produced by a benchmark/eval run.
    UI surfaces (artifact list responses' ``pending_*`` fields,
    ``search_soft_calls`` defaults) filter eval entries out so dormant
    eval writes never appear as actionable pending state. When
    ``eval`` is None (the default), the value comes from the
    ``glow_eval_mode`` contextvar — flipped at the top of an eval run
    in ``execute_with_emit`` — so the 300+ impl callsites inherit
    correctly without per-callsite plumbing. Passing ``eval=True``
    explicitly forces the flag on regardless of context.
    """
    if status not in ("pending", "accepted", "rejected"):
        raise ValueError(f"Invalid status: {status!r}")

    if eval is None:
        from app.infra.events.eval_context import is_eval_mode
        eval = is_eval_mode()

    patch_json = json.dumps(patch) if patch is not None else None

    row = await conn.fetchrow(
        """
        INSERT INTO soft_calls_entry
            (id, call_id, artifact, operation, status, artifact_id, patch, active, mcp, generated, eval)
        VALUES (COALESCE($1, uuidv7()), $2, $3, $4, $5, $6, $7::jsonb, $8, $9, true, $10)
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
        eval,
    )

    if row is None:
        raise ValueError("Failed to create soft_calls_entry row")

    entry_id = row["id"]
    created_at = row["created_at"]

    fresh_row = GetSoftCallResponse(
        id=entry_id,
        call_id=call_id,
        artifact=artifact,
        operation=operation,
        status=status,
        artifact_id=artifact_id,
        patch=patch,
        created_at=created_at,
        eval=eval,
    ).model_dump(mode="json")
    score = int(created_at.timestamp() * 1000)  # ms-precision matches MV ORDER BY

    # Write-back via the shared helper so this SETEX+ZADD participates in the
    # write-back deferral when issued inside a ``transaction_with_writeback``
    # (HC2/V2). Outside any transaction it writes immediately — unchanged
    # behaviour. The recent-index key/cap match the helper's defaults, and the
    # per-row key matches what get.py/search.py read back.
    await write_back_row(redis, _ENTRY, call_id, fresh_row, score_ms=score)

    return CreateSoftCallResponse(id=entry_id)
