"""Tests for resolve_soft_call — the atomic soft-call ack transition (A3/A4).

The soft-call ledger is INSERT-only; ``resolve_soft_call`` collapses the old
"read latest → assert pending → append terminal row" sequence into ONE atomic
conditional INSERT guarded by ``NOT EXISTS (... status <> 'pending')``, with the
partial-unique index ``soft_calls_entry_terminal_call_uidx`` as the hard
backstop against the check→insert race under true concurrency.

These tests pin:
  - A3: a second resolve on an already-resolved call writes 0 rows and returns
    ``None`` (the caller then SKIPS the side effect — no double ack).
  - A3 backstop: the partial-unique index permits at most one terminal row per
    call_id, so a concurrent committer that also passed the NOT EXISTS guard is
    rejected at COMMIT (mapped to ``None`` by resolve_soft_call).
"""

from __future__ import annotations

import asyncpg
import pytest

from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.resolve import resolve_soft_call

pytestmark = pytest.mark.asyncio


async def _seed_pending(conn, redis_client, *, call_id):
    """Append a pending ledger row for ``call_id`` (the propose write)."""
    from uuid import uuid4

    await create_soft_call(
        conn,
        redis_client,
        call_id=call_id,
        artifact="attempt",
        operation="complete",
        artifact_id=uuid4(),
        status="pending",
        patch={"completion_id": str(uuid4())},
    )


async def test_resolve_transitions_pending_to_accepted(conn, redis_client, call_id):
    """First resolve on a pending call returns the terminal row + flips status."""
    await _seed_pending(conn, redis_client, call_id=call_id)

    resolved = await resolve_soft_call(
        conn, redis_client, call_id=call_id, artifact="attempt",
        operation="complete", artifact_id=call_id, accept=True,
    )
    assert resolved is not None
    assert resolved.status == "accepted"

    # A terminal ledger row was appended (the MV isn't refreshed in this unit
    # test, so assert against the base table directly).
    status = await conn.fetchval(
        "SELECT status FROM soft_calls_entry "
        "WHERE call_id = $1 AND status <> 'pending'",
        call_id,
    )
    assert status == "accepted"


async def test_resolve_second_ack_returns_none_no_double(conn, redis_client, call_id):
    """A second resolve (concurrent double-ack, serialized) returns None — the
    caller gates the side effect on a non-None result, so it applies AT MOST
    ONCE. Exactly one terminal row exists."""
    await _seed_pending(conn, redis_client, call_id=call_id)

    first = await resolve_soft_call(
        conn, redis_client, call_id=call_id, artifact="attempt",
        operation="complete", artifact_id=call_id, accept=True,
    )
    second = await resolve_soft_call(
        conn, redis_client, call_id=call_id, artifact="attempt",
        operation="complete", artifact_id=call_id, accept=True,
    )

    assert first is not None  # winner applies the side effect
    assert second is None  # loser skips — no double side effect

    # Exactly one terminal (non-pending) ledger row.
    n_terminal = await conn.fetchval(
        "SELECT count(*) FROM soft_calls_entry "
        "WHERE call_id = $1 AND status <> 'pending'",
        call_id,
    )
    assert n_terminal == 1


async def test_resolve_reject_after_accept_returns_none(conn, redis_client, call_id):
    """Once accepted, a subsequent reject (or any terminal transition) is a
    no-op (None) — the call is already terminal."""
    await _seed_pending(conn, redis_client, call_id=call_id)

    await resolve_soft_call(
        conn, redis_client, call_id=call_id, artifact="attempt",
        operation="complete", artifact_id=call_id, accept=True,
    )
    rejected = await resolve_soft_call(
        conn, redis_client, call_id=call_id, artifact="attempt",
        operation="complete", artifact_id=call_id, accept=False,
    )
    assert rejected is None


async def test_partial_unique_index_blocks_second_terminal(conn, redis_client, call_id):
    """The partial-unique index is the hard backstop: it permits AT MOST ONE
    terminal row per call_id. Simulates the lost concurrency race where two
    transactions both pass the NOT EXISTS guard — the second terminal insert is
    rejected with a unique violation (which resolve_soft_call maps to None)."""
    await _seed_pending(conn, redis_client, call_id=call_id)

    # One terminal row (the winner).
    await conn.execute(
        "INSERT INTO soft_calls_entry "
        "(call_id, artifact, operation, status, artifact_id) "
        "VALUES ($1, 'attempt', 'complete', 'accepted', $1)",
        call_id,
    )
    # A second terminal insert (the racer that also passed NOT EXISTS) is
    # rejected by the index — never two acks applied.
    with pytest.raises(asyncpg.UniqueViolationError):
        await conn.execute(
            "INSERT INTO soft_calls_entry "
            "(call_id, artifact, operation, status, artifact_id) "
            "VALUES ($1, 'attempt', 'complete', 'rejected', $1)",
            call_id,
        )


async def test_pending_rows_unconstrained(conn, redis_client, call_id):
    """Multiple pending rows for the same call_id are legal (propose + retries);
    the partial-unique index only constrains terminal rows."""
    from uuid import uuid4

    for _ in range(3):
        await conn.execute(
            "INSERT INTO soft_calls_entry "
            "(call_id, artifact, operation, status, artifact_id) "
            "VALUES ($1, 'attempt', 'complete', 'pending', $2)",
            call_id,
            uuid4(),
        )
    n_pending = await conn.fetchval(
        "SELECT count(*) FROM soft_calls_entry "
        "WHERE call_id = $1 AND status = 'pending'",
        call_id,
    )
    assert n_pending == 3
