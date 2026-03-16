"""Tests for search_homes."""

import pytest

from app.tools.entries.home.create import create_home
from app.tools.entries.home.refresh import refresh_home
from app.tools.entries.home.search import search_homes
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _setup(conn, profile_id, bundle):
    session = await create_session(conn, profile_id=profile_id)
    result = await create_home(
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
    return result


async def test_finds_created_entry(conn, profile_id, simulation_bundle):
    result = await _setup(conn, profile_id, simulation_bundle)
    await refresh_home(conn)

    items = await search_homes(conn)

    ids = [item.id for item in items]
    assert result.id in ids


async def test_pagination_limit(conn, profile_id, simulation_bundle):
    await _setup(conn, profile_id, simulation_bundle)
    await refresh_home(conn)

    items = await search_homes(conn, limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, profile_id, simulation_bundle):
    await _setup(conn, profile_id, simulation_bundle)
    await refresh_home(conn)

    items = await search_homes(conn)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, profile_id, simulation_bundle):
    result = await _setup(conn, profile_id, simulation_bundle)

    items = await search_homes(conn, bypass_mv=True)

    ids = [item.id for item in items]
    assert result.id in ids
