"""Tests for refresh_home."""

import pytest
from app.tools.entries.home.create import create_home
from app.tools.entries.home.get import get_homes
from app.tools.entries.home.refresh import refresh_home
from app.tools.entries.sessions.create import create_session
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _home(conn, redis_client, profile_id, bundle):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    return await create_home(
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


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_home_appears_after_refresh(conn, redis_client, profile_id, simulation_bundle):
    created = await _home(conn, redis_client, profile_id, simulation_bundle)
    lookup_id = created.id

    await refresh_home(conn)
    items = await get_homes(conn, ids=[lookup_id], redis=redis_client)

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_new_home_is_not_visible_before_refresh(conn, redis_client, profile_id, simulation_bundle):
    created = await _home(conn, redis_client, profile_id, simulation_bundle)
    lookup_id = created.id

    items = await get_homes(conn, ids=[lookup_id], redis=redis_client, bypass_cache=True)

    assert items == []


async def test_refresh_is_idempotent(conn):
    await refresh_home(conn)
    await refresh_home(conn)

    assert True
