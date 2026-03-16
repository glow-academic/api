"""Tests for refresh_attempt_practice."""

import pytest

from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_practice.create import create_attempt_practice
from app.tools.entries.attempt_practice.get import get_attempt_practice
from app.tools.entries.attempt_practice.refresh import (
    refresh_attempt_practice,
)
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.persona.create import create_persona
from app.tools.entries.practice.create import create_practice
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
        practice=True,
    )
    practice = await create_practice(
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
    return await create_attempt_practice(
        conn,
        attempt_id=attempt.id,
        practice_id=practice.id,
        session_id=session.id,
    )


async def test_appears_after_refresh(conn, profile_id, simulation_bundle):
    result = await _setup(conn, profile_id, simulation_bundle)
    await refresh_attempt_practice(conn)

    items = await get_attempt_practice(conn, attempt_ids=[result.attempt_id])
    assert len(items) >= 1


async def test_not_visible_before_refresh(conn, profile_id, simulation_bundle):
    result = await _setup(conn, profile_id, simulation_bundle)

    items = await get_attempt_practice(conn, attempt_ids=[result.attempt_id])
    assert len(items) == 0
