"""Tests for search_attempt_homes."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_home.create import create_attempt_home
from app.tools.entries.attempt_home.refresh import refresh_attempt_home
from app.tools.entries.attempt_home.search import search_attempt_homes
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.home.create import create_home
from app.tools.entries.persona.create import create_persona
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _setup(conn, profile_id, bundle):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    call = await create_call(conn, run_id=run.id, session_id=session.id)
    persona = await create_persona(conn)
    attempt = await create_attempt(
        conn,
        call_id=call.id,
        user_persona_id=persona.id,
        profiles_id=profile_id,
    )
    home = await create_home(
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
    result = await create_attempt_home(
        conn, attempt_id=attempt.id, home_id=home.id, session_id=session.id
    )
    return result, attempt, home


async def test_finds_created_entry(conn, profile_id, simulation_bundle):
    result, attempt, _ = await _setup(conn, profile_id, simulation_bundle)
    await refresh_attempt_home(conn)

    items = await search_attempt_homes(conn, attempt_ids=[attempt.id])

    attempt_ids = [item.attempt_id for item in items]
    assert result.attempt_id in attempt_ids


async def test_filters_by_attempt_id(conn, profile_id, simulation_bundle):
    await _setup(conn, profile_id, simulation_bundle)
    await refresh_attempt_home(conn)

    items = await search_attempt_homes(conn, attempt_ids=[nonexistent_id()])

    assert items == []


async def test_filters_by_home_id(conn, profile_id, simulation_bundle):
    result, _, home = await _setup(conn, profile_id, simulation_bundle)
    await refresh_attempt_home(conn)

    items = await search_attempt_homes(conn, home_ids=[home.id])

    home_ids = [item.home_id for item in items]
    assert result.home_id in home_ids


async def test_pagination_limit(conn, profile_id, simulation_bundle):
    await _setup(conn, profile_id, simulation_bundle)
    await refresh_attempt_home(conn)

    items = await search_attempt_homes(conn, limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, profile_id, simulation_bundle):
    await _setup(conn, profile_id, simulation_bundle)
    await refresh_attempt_home(conn)

    items = await search_attempt_homes(conn)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, profile_id, simulation_bundle):
    result, attempt, _ = await _setup(conn, profile_id, simulation_bundle)

    items = await search_attempt_homes(conn, attempt_ids=[attempt.id], bypass_mv=True)

    attempt_ids = [item.attempt_id for item in items]
    assert result.attempt_id in attempt_ids
