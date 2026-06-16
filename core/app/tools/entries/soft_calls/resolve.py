"""Soft calls RESOLVE — atomic terminal-state transition (pending → accepted/rejected).

The soft-call ledger (``create.py``) is INSERT-only: each state change appends a
new row and ``soft_calls_mv`` keeps the latest per ``call_id``. The three ack
sites (attempt complete / attempt start / auth update) used to read the latest
row, assert ``status == 'pending'``, apply a side effect, then ``create_soft_call``
a terminal row — with NO serialization (A3). Two concurrent acks both read
``pending``, both applied the side effect, both appended a terminal row.

``resolve_soft_call`` collapses the assert-pending + terminal-insert into ONE
atomic conditional INSERT:

    INSERT INTO soft_calls_entry (...terminal...)
    SELECT ... WHERE NOT EXISTS (
        SELECT 1 FROM soft_calls_entry
        WHERE call_id = $k AND status <> 'pending'
    )
    RETURNING id, created_at

If a terminal row already exists for the call_id the INSERT writes 0 rows and
returns ``None`` — the caller treats that as "already resolved" and SKIPS the
side effect (no double activate). The partial-unique index
``soft_calls_entry_terminal_call_uidx`` (call_id WHERE status <> 'pending') is
the hard backstop: under true concurrency, if two transactions both pass the
NOT EXISTS guard, the second to commit hits a unique violation, which is
likewise mapped to ``None`` (already resolved).

Caller contract (A4): run this INSIDE the same ``conn.transaction()`` as the
``activate_rows`` side effect, so a crash between activate and ledger commit
can't leave activated rows with a stale ``pending`` ledger. Run the MV
``refresh_*`` only AFTER that transaction commits. On ``None`` (already
resolved) the caller must NOT have applied — gate the side effect on the result.
"""

import json
from typing import Any
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.soft_calls.types import GetSoftCallResponse
from app.utils.cache.hedged_row import write_back_row

# Cache namespace shared with create.py/get.py/search.py — see create.py for the
# key-shape rationale. Routing the terminal-state write-back through
# ``write_back_row`` makes it participate in the HC2/V2 deferral.
_ENTRY = "soft_call"


async def resolve_soft_call(
    conn: asyncpg.Connection,
    redis: Redis,
    *,
    call_id: UUID,
    artifact: str,
    operation: str,
    artifact_id: UUID,
    accept: bool,
    patch: dict[str, Any] | None = None,
    mcp: bool = False,
    eval: bool | None = None,
) -> GetSoftCallResponse | None:
    """Atomically transition a pending soft-call to its terminal state.

    Returns the freshly-written terminal ``GetSoftCallResponse`` on success, or
    ``None`` when the call was already resolved (a terminal row already exists,
    or a concurrent committer won the race). The caller MUST gate any side
    effect on a non-``None`` result so a double-ack applies the side effect at
    most once.

    Must run inside the caller's ``conn.transaction()`` (alongside the activate
    side effect) so the ledger commit is atomic with it.
    """
    status = "accepted" if accept else "rejected"

    if eval is None:
        from app.infra.events.eval_context import is_eval_mode
        eval = is_eval_mode()

    patch_json = json.dumps(patch) if patch is not None else None

    try:
        row = await conn.fetchrow(
            """
            INSERT INTO soft_calls_entry
                (call_id, artifact, operation, status, artifact_id, patch,
                 active, mcp, generated, eval)
            SELECT $1, $2, $3, $4, $5, $6::jsonb, true, $7, true, $8
            WHERE NOT EXISTS (
                SELECT 1 FROM soft_calls_entry
                WHERE call_id = $1 AND status <> 'pending'
            )
            RETURNING id, created_at
            """,
            call_id,
            artifact,
            operation,
            status,
            artifact_id,
            patch_json,
            mcp,
            eval,
        )
    except asyncpg.UniqueViolationError:
        # Concurrent committer won the terminal-insert race (both passed the
        # NOT EXISTS guard, the partial-unique index rejected the loser).
        # Already resolved.
        return None

    if row is None:
        # A terminal row already existed — already resolved.
        return None

    entry = GetSoftCallResponse(
        id=row["id"],
        call_id=call_id,
        artifact=artifact,
        operation=operation,
        status=status,
        artifact_id=artifact_id,
        patch=patch,
        created_at=row["created_at"],
        eval=eval,
    )

    # Write-back cache + recent-index, identical shape to create_soft_call so
    # get_soft_call / search_soft_calls see the terminal state immediately.
    # ``resolve_soft_call`` runs INSIDE the caller's ``conn.transaction()`` (A4),
    # so this write-back is the exact V2-GAP case: routing it through
    # ``write_back_row`` defers the SETEX until that transaction COMMITS when the
    # caller uses ``transaction_with_writeback``. A rollback then leaves NO
    # phantom terminal cache row (previously the raw pipeline fired the SETEX
    # immediately, serving a non-existent terminal status for the TTL).
    score = int(row["created_at"].timestamp() * 1000)
    await write_back_row(
        redis, _ENTRY, call_id, entry.model_dump(mode="json"), score_ms=score
    )

    return entry
