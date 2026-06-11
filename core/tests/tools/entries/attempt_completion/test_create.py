"""Tests for create_attempt_completion."""

import pytest

from app.tools.entries.attempt_completion.create import create_attempt_completion
from app.tools.entries.attempt_completion.refresh import refresh_attempt_completion
from app.tools.entries.attempt_completion.refresh import MV_NAME
from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.persona.create import create_persona
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _setup_entry(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    persona = await create_persona(conn, redis_client)
    seed = await create_attempt(conn, redis_client, session_id=session.id, user_persona_id=persona.id, profiles_id=profile_id)
    return session, seed


async def test_create_returns_id(conn, redis_client, profile_id):
    session, seed = await _setup_entry(conn, redis_client, profile_id)
    result = await create_attempt_completion(conn, redis_client, attempt_id=seed.id, session_id=session.id)

    assert result.id is not None


async def test_row_not_visible_before_refresh(conn, redis_client, profile_id):
    session, seed = await _setup_entry(conn, redis_client, profile_id)
    result = await create_attempt_completion(conn, redis_client, attempt_id=seed.id, session_id=session.id)

    row = await conn.fetchrow(f"SELECT id FROM {MV_NAME} WHERE id = $1", result.id)

    assert row is None


async def test_refresh_exposes_created_row(conn, redis_client, profile_id):
    session, seed = await _setup_entry(conn, redis_client, profile_id)
    result = await create_attempt_completion(conn, redis_client, attempt_id=seed.id, session_id=session.id, mcp=True)
    await refresh_attempt_completion(conn)

    row = await conn.fetchrow(f"SELECT id, mcp FROM {MV_NAME} WHERE id = $1", result.id)

    assert row is not None
    assert row['id'] == result.id
    assert row['mcp'] is True


# --- B1: soft-completion proposal must not permanently wedge the hard path ---


async def test_soft_proposal_reports_not_active(conn, redis_client, profile_id):
    """A soft proposal occupies the unique slot but is MV-invisible — it must
    report active=False so the caller knows the attempt is NOT yet completed."""
    session, seed = await _setup_entry(conn, redis_client, profile_id)

    soft = await create_attempt_completion(
        conn, redis_client, attempt_id=seed.id, session_id=session.id, soft=True
    )

    assert soft.active is False
    db_active = await conn.fetchval(
        "SELECT active FROM attempt_completion_entry WHERE attempt_id = $1", seed.id
    )
    assert db_active is False


async def test_hard_complete_supersedes_dormant_soft(conn, redis_client, profile_id):
    """B1 core: soft-then-hard. The hard complete must supersede the dormant
    proposal (active=true, MV-visible), not no-op on a wedged dormant row."""
    session, seed = await _setup_entry(conn, redis_client, profile_id)

    soft = await create_attempt_completion(
        conn, redis_client, attempt_id=seed.id, session_id=session.id, soft=True
    )
    hard = await create_attempt_completion(
        conn, redis_client, attempt_id=seed.id, session_id=session.id, soft=False
    )
    await refresh_attempt_completion(conn)

    # Same unique slot, now active and reported as a real completion.
    assert hard.id == soft.id
    assert hard.active is True

    mv_row = await conn.fetchrow(f"SELECT id FROM {MV_NAME} WHERE attempt_id = $1", seed.id)
    assert mv_row is not None  # MV now shows the attempt completed
    assert mv_row["id"] == soft.id


async def test_hard_complete_does_not_clobber_accepted(conn, redis_client, profile_id):
    """An already-accepted (active=true) completion must NOT be clobbered by a
    later hard complete — the first accepted row stands, no supersede."""
    session, seed = await _setup_entry(conn, redis_client, profile_id)

    first = await create_attempt_completion(
        conn, redis_client, attempt_id=seed.id, session_id=session.id,
        soft=False, message="first",
    )
    second = await create_attempt_completion(
        conn, redis_client, attempt_id=seed.id, session_id=session.id,
        soft=False, message="second",
    )

    assert second.id == first.id
    assert second.active is True
    msg = await conn.fetchval(
        "SELECT message FROM attempt_completion_entry WHERE attempt_id = $1", seed.id
    )
    assert msg == "first"  # the accepted completion was not overwritten


async def test_soft_does_not_downgrade_accepted(conn, redis_client, profile_id):
    """A soft proposal arriving after an accepted completion must not downgrade
    or touch the active row."""
    session, seed = await _setup_entry(conn, redis_client, profile_id)

    await create_attempt_completion(
        conn, redis_client, attempt_id=seed.id, session_id=session.id, soft=False
    )
    late_soft = await create_attempt_completion(
        conn, redis_client, attempt_id=seed.id, session_id=session.id, soft=True
    )

    assert late_soft.active is True  # reports the row's TRUE (still-active) state
    db_active = await conn.fetchval(
        "SELECT active FROM attempt_completion_entry WHERE attempt_id = $1", seed.id
    )
    assert db_active is True
