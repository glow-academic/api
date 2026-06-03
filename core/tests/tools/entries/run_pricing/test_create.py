"""Tests for run_pricing entry."""

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.run_pricing.create import (
    create_run_pricing_entry_internal,
)
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.resources.pricing.create import create_pricing

pytestmark = pytest.mark.asyncio


async def _run(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, session_id=session.id, group_id=group.id)
    return session, run


# pricing_type is a plain text column ('input' | 'output' | 'cached'); the
# legacy enum type was dropped.
PRICING_TYPE = "input"


async def test_create_returns_id(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)

    entry_id = await conn.fetchval(
        "INSERT INTO run_pricing_entry (pricing_type, count, run_id, session_id) VALUES ($1, $2, $3, $4) RETURNING id",
        PRICING_TYPE,
        5,
        run.id,
        session.id,
    )

    assert entry_id is not None


async def test_roundtrip_via_db(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)

    entry_id = await conn.fetchval(
        "INSERT INTO run_pricing_entry (pricing_type, count, run_id, session_id) VALUES ($1, $2, $3, $4) RETURNING id",
        PRICING_TYPE,
        5,
        run.id,
        session.id,
    )

    row = await conn.fetchrow("SELECT * FROM run_pricing_entry WHERE id = $1", entry_id)

    assert row is not None
    assert row["id"] == entry_id
    assert row["pricing_type"] == PRICING_TYPE
    assert row["count"] == 5
    assert row["run_id"] == run.id
    assert row["session_id"] == session.id
    assert row["active"] is True
    assert row["mcp"] is False


async def test_helper_links_pricing_resource(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    pricing = await create_pricing(
        conn,
        "input",
        0.02,
        "tokens",
        "tokens",
        1000,
        redis_client,
    )

    result = await create_run_pricing_entry_internal(
        conn,
        redis_client, session_id=session.id,
        pricing_type="input",
        run_id=run.id,
        pricing_id=pricing.id,
        count=5,
    )

    linked_pricing_id = await conn.fetchval(
        """
        SELECT pricing_id
        FROM run_pricing_pricing_connection
        WHERE run_pricing_id = $1
        """,
        result.id,
    )

    assert linked_pricing_id == pricing.id
