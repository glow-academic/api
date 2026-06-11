"""search_messages deterministic reasoning↔answer ordering — H3.

Real DB; deps injected (conn/redis/profile_id/tmp_path).

A reasoning trace and its answer for the same turn can share an identical
``message_created_at``. With only a timestamp sort the two tie and replay in
either order. The fix adds a stable tiebreaker (reasoning row first, then
message_id) so the order is deterministic across both the SQL ASC path and the
hedged DESC path.
"""

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.messages.search import search_messages
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.infra.websocket.persist_run_message import persist_run_message
from datetime import datetime, timezone

pytestmark = pytest.mark.asyncio


async def _seed_tied_turn(conn, redis_client, profile_id, tmp_path):
    """Persist a reasoning row + answer row with the SAME created_at (a tie)."""
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(
        conn, redis_client, session_id=session.id, artifact_type="persona"
    )
    run = await create_run(
        conn, redis_client, group_id=group.id, session_id=session.id,
    )
    tie = datetime(2030, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    # Answer first, reasoning second — but with the same timestamp the ORDER
    # must be decided by the tiebreaker, not insertion order.
    await persist_run_message(
        conn, redis_client, run_id=run.id, session_id=session.id,
        role="assistant", content="ANSWER", upload_folder=tmp_path,
        created_at=tie,
    )
    await persist_run_message(
        conn, redis_client, run_id=run.id, session_id=session.id,
        role="assistant", content="REASONING", upload_folder=tmp_path,
        reasoning=True, created_at=tie,
    )
    await conn.execute("REFRESH MATERIALIZED VIEW messages_mv")
    return run


async def test_asc_reasoning_precedes_answer_on_tie(
    conn, redis_client, profile_id, tmp_path
):
    run = await _seed_tied_turn(conn, redis_client, profile_id, tmp_path)
    rows, _ = await search_messages(
        conn, redis_client, run_ids=[run.id], sort_order="asc", limit=50,
    )
    # Reasoning row sorts before the answer row deterministically.
    reasoning_idx = next(i for i, r in enumerate(rows) if r.reasoning)
    answer_idx = next(i for i, r in enumerate(rows) if not r.reasoning)
    assert reasoning_idx < answer_idx


async def test_order_is_stable_across_repeated_queries(
    conn, redis_client, profile_id, tmp_path
):
    run = await _seed_tied_turn(conn, redis_client, profile_id, tmp_path)
    orders = []
    for _ in range(5):
        rows, _ = await search_messages(
            conn, redis_client, run_ids=[run.id], sort_order="asc", limit=50,
            bypass_cache=True,
        )
        orders.append([str(r.message_id) for r in rows])
    assert all(o == orders[0] for o in orders), "ASC order must be deterministic"


async def test_desc_order_is_deterministic_on_tie(
    conn, redis_client, profile_id, tmp_path
):
    run = await _seed_tied_turn(conn, redis_client, profile_id, tmp_path)
    orders = []
    for _ in range(5):
        rows, _ = await search_messages(
            conn, redis_client, run_ids=[run.id], sort_order="desc", limit=50,
            bypass_cache=True,
        )
        orders.append([str(r.message_id) for r in rows])
    assert all(o == orders[0] for o in orders), "DESC order must be deterministic"
