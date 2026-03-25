"""Tests for search_runs."""

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.run_pricing.create import (
    create_run_pricing_entry_internal,
)
from app.tools.entries.runs.create import create_run
from app.tools.entries.runs.search import search_runs
from app.tools.entries.sessions.create import create_session
from app.tools.resources.pricing.create import create_pricing

pytestmark = pytest.mark.asyncio


async def test_search_includes_pricing_counts(conn, profile_id, redis_client):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, session_id=session.id, group_id=group.id)
    input_pricing = await create_pricing(
        conn,
        "input",
        0.02,
        "tokens",
        "tokens",
        1000,
        redis_client,
    )
    output_pricing = await create_pricing(
        conn,
        "output",
        0.03,
        "tokens",
        "tokens",
        1000,
        redis_client,
    )
    await create_run_pricing_entry_internal(
        conn,
        session_id=session.id,
        pricing_type="input",
        run_id=run.id,
        pricing_id=input_pricing.id,
        count=11,
    )
    await create_run_pricing_entry_internal(
        conn,
        session_id=session.id,
        pricing_type="output",
        run_id=run.id,
        pricing_id=output_pricing.id,
        count=7,
    )

    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY runs_mv")

    items, total_count = await search_runs(conn, group_ids=[group.id], limit=10)

    assert total_count == 1
    assert items[0].run_id == run.id
    assert {item.count for item in items[0].pricing} == {11, 7}
