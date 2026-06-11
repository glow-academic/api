"""Integrity tests for benchmark sync (E3).

Covers the two data-integrity hazards the sync was hardened against:

  * ATOMIC — a partial invocation failure must leave NO committed benchmark
    or invocation scaffold (all-or-nothing), not benchmark + 1..N-1.
  * IDEMPOTENT — re-running sync for the same eval (as ``/eval/update`` does
    on every save) must REPLACE the prior generated scaffold, not append a
    duplicate, and must leave OTHER evals' benchmarks untouched.

These exercise the real ``pool.acquire() -> conn.transaction()`` path against
the test Postgres so the transaction + scoped-deactivation semantics are
verified for real, not mocked.
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest

pytestmark = pytest.mark.asyncio


async def _make_eval(conn) -> UUID:
    """Insert a minimal evals_resource row (defaults cover the rest)."""
    row = await conn.fetchrow(
        "INSERT INTO evals_resource DEFAULT VALUES RETURNING id"
    )
    return row["id"]


async def _make_model(conn) -> UUID:
    row = await conn.fetchrow(
        "INSERT INTO models_resource (value) VALUES ($1) RETURNING id",
        "test-model",
    )
    return row["id"]


async def _active_benchmark_ids(conn, evals_id: UUID) -> list[UUID]:
    """Active generated benchmark_entry ids linked to this eval (the MV gate)."""
    rows = await conn.fetch(
        """
        SELECT be.id
        FROM benchmark_entry be
        JOIN benchmark_evals_connection bec
          ON bec.benchmark_id = be.id AND bec.active = true
        WHERE bec.evals_id = $1 AND be.active = true
        """,
        evals_id,
    )
    return [r["id"] for r in rows]


async def _active_invocation_count(conn, benchmark_ids: list[UUID]) -> int:
    if not benchmark_ids:
        return 0
    row = await conn.fetchrow(
        "SELECT count(*) AS n FROM invocation_entry "
        "WHERE benchmark_id = ANY($1) AND active = true",
        benchmark_ids,
    )
    return row["n"]


async def test_sync_partial_invocation_failure_is_atomic(pool, redis_client, monkeypatch):
    """If invocation N fails, neither the benchmark nor any invocation persists."""
    from app.infra.benchmark import sync as sync_mod

    async with pool.acquire() as conn:
        eval_id = await _make_eval(conn)
        m1 = await _make_model(conn)
        m2 = await _make_model(conn)

    # Make the SECOND create_invocation blow up mid-chain.
    from app.tools.entries.invocation import create as inv_create_mod
    real = inv_create_mod.create_invocation
    calls = {"n": 0}

    async def boom(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("simulated mid-chain invocation failure")
        return await real(*args, **kwargs)

    monkeypatch.setattr(inv_create_mod, "create_invocation", boom)

    with pytest.raises(RuntimeError, match="simulated mid-chain"):
        await sync_mod.sync_benchmark_entries(
            pool,
            eval_id,
            model_ids=[m1, m2],
            model_flag_ids=[],
            model_rubric_ids=[],
            model_position_ids=[],
            department_ids=[],
        )

    # Atomic: the whole scaffold rolled back — no benchmark, no invocations.
    async with pool.acquire() as conn:
        bids = await _active_benchmark_ids(conn, eval_id)
        assert bids == [], f"expected no committed benchmark, got {bids}"
        # Even querying ALL invocations (active or not) for any benchmark that
        # might have linked this eval should be empty since nothing committed.
        any_inv = await conn.fetchrow(
            """
            SELECT count(*) AS n FROM invocation_entry ie
            JOIN benchmark_evals_connection bec
              ON bec.benchmark_id = ie.benchmark_id
            WHERE bec.evals_id = $1
            """,
            eval_id,
        )
        assert any_inv["n"] == 0


async def test_sync_is_idempotent_on_rerun(pool, redis_client):
    """A second sync for the same eval REPLACES — no duplicate scaffold."""
    from app.infra.benchmark.sync import sync_benchmark_entries

    async with pool.acquire() as conn:
        eval_id = await _make_eval(conn)
        m1 = await _make_model(conn)
        m2 = await _make_model(conn)

    # First run.
    n1 = await sync_benchmark_entries(
        pool, eval_id, model_ids=[m1, m2],
        model_flag_ids=[], model_rubric_ids=[], model_position_ids=[],
        department_ids=[],
    )
    assert n1 == 2

    async with pool.acquire() as conn:
        bids1 = await _active_benchmark_ids(conn, eval_id)
        assert len(bids1) == 1
        assert await _active_invocation_count(conn, bids1) == 2

    # Second run (as /eval/update would). Must replace, not append.
    n2 = await sync_benchmark_entries(
        pool, eval_id, model_ids=[m1, m2],
        model_flag_ids=[], model_rubric_ids=[], model_position_ids=[],
        department_ids=[],
    )
    assert n2 == 2

    async with pool.acquire() as conn:
        bids2 = await _active_benchmark_ids(conn, eval_id)
        # Exactly ONE active benchmark remains (the fresh one), not two.
        assert len(bids2) == 1, f"expected 1 active benchmark, got {len(bids2)}"
        # It is a NEW benchmark — the prior one was deactivated (replaced).
        assert bids2[0] != bids1[0]
        # Exactly 2 active invocations (the fresh set), not 4.
        assert await _active_invocation_count(conn, bids2) == 2
        # The prior benchmark is now inactive (deactivated, not deleted).
        prior_active = await conn.fetchrow(
            "SELECT active FROM benchmark_entry WHERE id = $1", bids1[0]
        )
        assert prior_active["active"] is False


async def test_sync_clear_is_scoped_to_this_eval(pool, redis_client):
    """Re-syncing eval A must not touch eval B's benchmark scaffold."""
    from app.infra.benchmark.sync import sync_benchmark_entries

    async with pool.acquire() as conn:
        eval_a = await _make_eval(conn)
        eval_b = await _make_eval(conn)
        m1 = await _make_model(conn)

    await sync_benchmark_entries(
        pool, eval_a, model_ids=[m1],
        model_flag_ids=[], model_rubric_ids=[], model_position_ids=[],
        department_ids=[],
    )
    await sync_benchmark_entries(
        pool, eval_b, model_ids=[m1],
        model_flag_ids=[], model_rubric_ids=[], model_position_ids=[],
        department_ids=[],
    )

    async with pool.acquire() as conn:
        b_before = await _active_benchmark_ids(conn, eval_b)
        assert len(b_before) == 1

    # Re-run eval A — eval B's scaffold must be unchanged.
    await sync_benchmark_entries(
        pool, eval_a, model_ids=[m1],
        model_flag_ids=[], model_rubric_ids=[], model_position_ids=[],
        department_ids=[],
    )

    async with pool.acquire() as conn:
        a_after = await _active_benchmark_ids(conn, eval_a)
        b_after = await _active_benchmark_ids(conn, eval_b)
        assert len(a_after) == 1  # A still has exactly one (replaced)
        assert b_after == b_before, "eval B's benchmark must be untouched"
