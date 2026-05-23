"""Tests for search_practices."""

import pytest

from app.tools.entries.practice.create import create_practice
from app.tools.entries.practice.refresh import refresh_practice
from app.tools.entries.practice.search import search_practices
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _setup(conn, redis_client, profile_id, bundle):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    result = await create_practice(
        conn,
        redis_client, session_id=session.id,
        cohorts_ids=[bundle.cohort_id],
        departments_ids=[bundle.department_id],
        simulations_ids=[bundle.simulation_id],
        profiles_ids=[profile_id],
        profile_personas_ids=[bundle.profile_persona_id],
        simulation_availability_ids=[bundle.simulation_availability_id],
        simulation_positions_ids=[bundle.simulation_position_id],
    )
    return result


async def test_finds_created_entry(conn, redis_client, profile_id, simulation_bundle):
    result = await _setup(conn, redis_client, profile_id, simulation_bundle)
    await refresh_practice(conn)

    items = await search_practices(conn, redis_client)

    ids = [item.id for item in items]
    assert result.id in ids


async def test_pagination_limit(conn, redis_client, profile_id, simulation_bundle):
    await _setup(conn, redis_client, profile_id, simulation_bundle)
    await refresh_practice(conn)

    items = await search_practices(conn, redis_client, limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, redis_client, profile_id, simulation_bundle):
    await _setup(conn, redis_client, profile_id, simulation_bundle)
    await refresh_practice(conn)

    items = await search_practices(conn, redis_client)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, redis_client, profile_id, simulation_bundle):
    result = await _setup(conn, redis_client, profile_id, simulation_bundle)

    items = await search_practices(conn, redis_client, bypass_mv=True)

    ids = [item.id for item in items]
    assert result.id in ids
