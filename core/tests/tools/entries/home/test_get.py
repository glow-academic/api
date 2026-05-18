"""Tests for get_homes."""

import pytest
from app.tools.entries.home.create import create_home
from app.tools.entries.home.get import get_homes
from app.tools.entries.home.refresh import refresh_home
from app.tools.entries.sessions.create import create_session
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _home(conn, profile_id, bundle):
    session = await create_session(conn, profile_id=profile_id)
    return await create_home(
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


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_home(conn, profile_id):
    _created(await _home(conn, profile_id))
    await refresh_home(conn)
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)
    items = await get_homes(conn, ids=[lookup_id])

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_returns_empty_for_missing_id(conn):
    items = await get_homes(conn, ids=[nonexistent_id()])

    assert items == []


async def test_returns_empty_for_empty_ids(conn):
    items = await get_homes(conn, ids=[])

    assert items == []
