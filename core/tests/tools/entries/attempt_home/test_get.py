"""Tests for get_attempt_home."""

import pytest
from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_home.create import create_attempt_home
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.home.create import create_home
from app.tools.entries.persona.create import create_persona
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.attempt_home.get import get_attempt_home
from app.tools.entries.attempt_home.refresh import refresh_attempt_home
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _attempt_home(conn, redis_client, profile_id, bundle, **overrides):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    call = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    persona = await create_persona(conn, redis_client)
    attempt = await create_attempt(
        conn,
        redis_client, session_id=session.id,
        user_persona_id=persona.id,
        profiles_id=profile_id,
    )
    home = await create_home(
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
    defaults = dict(attempt_id=attempt.id, home_id=home.id, session_id=session.id)
    defaults.update(overrides)
    result = await create_attempt_home(conn, redis_client, **defaults)
    return result, attempt, home


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_attempt_home(conn, redis_client, profile_id, simulation_bundle):
    created, _, _ = await _attempt_home(conn, redis_client, profile_id, simulation_bundle)
    await refresh_attempt_home(conn)
    lookup_id = created.attempt_id
    items = await get_attempt_home(conn, attempt_ids=[lookup_id], redis=redis_client)

    assert len(items) >= 1
    assert items[0].attempt_id == lookup_id


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_attempt_home(conn, attempt_ids=[nonexistent_id()], redis=redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_attempt_home(conn, attempt_ids=[], redis=redis_client)

    assert items == []
