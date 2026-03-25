"""Tests for create_attempt."""

import pytest

from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt.get import get_attempts
from app.tools.entries.attempt.refresh import refresh_attempt
from app.tools.entries.attempt_practice.create import create_attempt_practice
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.persona.create import create_persona
from app.tools.entries.practice.create import create_practice
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _attempt(conn, profile_id, **overrides):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    call = await create_call(conn, run_id=run.id, session_id=session.id)
    persona = await create_persona(conn)
    defaults = dict(
        call_id=call.id,
        user_persona_id=persona.id,
        profiles_id=profile_id,
    )
    defaults.update(overrides)
    result = await create_attempt(conn, **defaults)
    return session, result


async def test_returns_id(conn, profile_id, simulation_bundle):
    _, result = await _attempt(conn, profile_id)

    assert result.id is not None


async def test_visible_via_get_after_refresh(conn, profile_id, simulation_bundle):
    _, result = await _attempt(conn, profile_id)
    await refresh_attempt(conn)

    items = await get_attempts(conn, [result.id])

    assert len(items) == 1
    assert items[0].attempt_id == result.id


async def test_num_chats_and_practice(conn, profile_id, simulation_bundle):
    """practice in MV is derived from attempt_practice_entry existence."""
    bundle = simulation_bundle
    session, result = await _attempt(conn, profile_id, num_chats=3, practice=True)
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
    await create_attempt_practice(
        conn,
        attempt_id=result.id,
        practice_id=practice.id,
        session_id=session.id,
    )
    await refresh_attempt(conn)

    items = await get_attempts(conn, [result.id])

    assert len(items) == 1
    assert items[0].num_chats == 3
    assert items[0].practice is True


async def test_passes_mcp_flag(conn, profile_id, simulation_bundle):
    _, result = await _attempt(conn, profile_id, mcp=True)

    row = await conn.fetchrow(
        "SELECT mcp FROM attempt_entry WHERE id = $1",
        result.id,
    )
    assert row is not None
    assert row["mcp"] is True
