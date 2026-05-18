"""Tests for create_practice."""

import pytest

from app.tools.entries.practice.create import create_practice
from app.tools.entries.practice.get import get_practices
from app.tools.entries.practice.refresh import refresh_practice
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _practice(conn, profile_id, bundle):
    session = await create_session(conn, profile_id=profile_id)
    return await create_practice(
        conn,
        session_id=session.id,
        cohorts_ids=[bundle.cohort_id],
        departments_ids=[bundle.department_id],
        simulations_ids=[bundle.simulation_id],
        profiles_ids=[profile_id],
        profile_personas_ids=[bundle.profile_persona_id],
        simulation_availability_ids=[bundle.simulation_availability_id],
        simulation_positions_ids=[bundle.simulation_position_id],
    )


async def test_returns_id(conn, profile_id, simulation_bundle):
    result = await _practice(conn, profile_id, simulation_bundle)

    assert result.id is not None


async def test_visible_via_get_after_refresh(conn, profile_id, simulation_bundle):
    result = await _practice(conn, profile_id, simulation_bundle)
    await refresh_practice(conn)

    items = await get_practices(conn, [result.id])

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].active is True


async def test_connections_populated(conn, profile_id, simulation_bundle):
    result = await _practice(conn, profile_id, simulation_bundle)
    await refresh_practice(conn)

    items = await get_practices(conn, [result.id])

    assert len(items) == 1
    practice = items[0]
    assert simulation_bundle.simulation_id in practice.simulation_ids
    assert simulation_bundle.cohort_id in practice.cohort_ids
    assert simulation_bundle.department_id in practice.department_ids
    assert profile_id in practice.profile_ids


async def test_passes_mcp_flag(conn, profile_id, simulation_bundle):
    bundle = simulation_bundle
    session = await create_session(conn, profile_id=profile_id)
    result = await create_practice(
        conn,
        session_id=session.id,
        cohorts_ids=[bundle.cohort_id],
        departments_ids=[bundle.department_id],
        simulations_ids=[bundle.simulation_id],
        profiles_ids=[profile_id],
        profile_personas_ids=[bundle.profile_persona_id],
        simulation_availability_ids=[bundle.simulation_availability_id],
        simulation_positions_ids=[bundle.simulation_position_id],
        mcp=True,
    )

    row = await conn.fetchrow(
        "SELECT mcp FROM practice_entry WHERE id = $1",
        result.id,
    )
    assert row is not None
    assert row["mcp"] is True
