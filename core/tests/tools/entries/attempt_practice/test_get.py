"""Tests for get_attempt_practice."""

import pytest
from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_practice.create import create_attempt_practice
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.persona.create import create_persona
from app.tools.entries.practice.create import create_practice
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.attempt_practice.get import get_attempt_practice
from app.tools.entries.attempt_practice.refresh import refresh_attempt_practice
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _attempt_practice(conn, redis_client, profile_id, bundle, **overrides):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    call = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    persona = await create_persona(conn, redis_client)
    attempt = await create_attempt(
        conn,
        redis_client, call_id=call.id,
        user_persona_id=persona.id,
        profiles_id=profile_id,
        practice=True,
    )
    practice = await create_practice(
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
    defaults = dict(
        attempt_id=attempt.id, practice_id=practice.id, session_id=session.id
    )
    defaults.update(overrides)
    result = await create_attempt_practice(conn, redis_client, **defaults)
    return result, attempt, practice


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_attempt_practice(conn, redis_client, profile_id):
    _created(await _attempt_practice(conn, redis_client, profile_id))
    await refresh_attempt_practice(conn)
    lookup_id = getattr(created, 'attempt_id', None) or getattr(created, 'id', None) or getattr(created, 'attempt', None)
    items = await get_attempt_practice(conn, redis_client, attempt_ids=[lookup_id])

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_attempt_practice(conn, redis_client, attempt_ids=[nonexistent_id()])

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_attempt_practice(conn, redis_client, attempt_ids=[])

    assert items == []
