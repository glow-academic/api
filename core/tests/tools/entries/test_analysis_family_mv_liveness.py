"""L1 regression: analysis-family MVs must honor own-row liveness.

The C6-A fix (calls_mv) + D1 fix (attempt_analysis_mv) added the missing
`active = true` liveness predicates, but the five analysis-family MVs that JOIN
attempt_message_entry (alias ``sm``) and attempt_chat_bridge_entry (alias
``ac``) still filtered only their own row + the chat (``c``) + the attempt
(``a``) — never ``sm.active`` / ``ac.active``. So soft-deleted / dormant message
+ chat-bridge rows leaked their dependent strengths / hints / improvements /
highlights / replacements into these hot reads.

This mirrors the calls_mv test: build a real attempt -> chat -> bridge ->
message chain, create one of each analysis-family row, assert all surface in
their MVs, then soft-deactivate the *message* (``sm``) — and in a second test
the *bridge* (``ac``) — and assert every dependent row drops out.
"""

import pytest

from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_chat_bridge.create import (
    create_attempt_chat_bridge,
)
from app.tools.entries.attempt_grade.create import create_attempt_grade
from app.tools.entries.attempt_highlight.create import create_attempt_highlight
from app.tools.entries.attempt_highlight.refresh import refresh_attempt_highlight
from app.tools.entries.attempt_hint.create import create_attempt_hint
from app.tools.entries.attempt_hint.refresh import refresh_attempt_hint
from app.tools.entries.attempt_improvement.create import (
    create_attempt_improvement,
)
from app.tools.entries.attempt_improvement.refresh import (
    refresh_attempt_improvement,
)
from app.tools.entries.attempt_message.create import create_attempt_message
from app.tools.entries.attempt_replacement.create import (
    create_attempt_replacement,
)
from app.tools.entries.attempt_replacement.refresh import (
    refresh_attempt_replacement,
)
from app.tools.entries.attempt_strength.create import create_attempt_strength
from app.tools.entries.attempt_strength.refresh import refresh_attempt_strength
from app.tools.entries.calls.create import create_call
from app.tools.entries.chat.create import create_chat
from app.tools.entries.groups.create import create_group
from app.tools.entries.persona.create import create_persona
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _setup(conn, redis_client, profile_id):
    """Full chain -> one of each analysis-family row. Returns a dict of ids."""
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(
        conn, redis_client, session_id=session.id, artifact_type="persona"
    )
    run = await create_run(
        conn, redis_client, group_id=group.id, session_id=session.id
    )
    await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    persona = await create_persona(conn, redis_client)
    attempt = await create_attempt(
        conn,
        redis_client,
        session_id=session.id,
        user_persona_id=persona.id,
        profiles_id=profile_id,
    )
    chat = await create_chat(conn, redis_client, session_id=session.id)
    attempt_chat = await create_attempt_chat(
        conn, redis_client, session_id=session.id, chat_id=chat.id
    )
    await create_attempt_chat_bridge(
        conn,
        redis_client,
        attempt_id=attempt.id,
        attempt_chat_id=attempt_chat.id,
        session_id=session.id,
    )
    message = await create_attempt_message(
        conn, redis_client, chat_id=attempt_chat.id, session_id=session.id
    )
    grade = await create_attempt_grade(
        conn,
        redis_client,
        chat_id=attempt_chat.id,
        session_id=session.id,
        time_taken=120,
        passed=True,
        score=85,
    )
    strength = await create_attempt_strength(
        conn,
        redis_client,
        grade_id=grade.id,
        message_id=message.id,
        session_id=session.id,
        name="Good greeting",
    )
    hint = await create_attempt_hint(
        conn,
        redis_client,
        message_id=message.id,
        session_id=session.id,
        hint="Try X",
    )
    improvement = await create_attempt_improvement(
        conn,
        redis_client,
        grade_id=grade.id,
        message_id=message.id,
        session_id=session.id,
        name="Pacing",
    )
    highlight = await create_attempt_highlight(
        conn,
        redis_client,
        strength_id=strength.id,
        session_id=session.id,
        section="intro",
    )
    replacement = await create_attempt_replacement(
        conn,
        redis_client,
        improvement_id=improvement.id,
        session_id=session.id,
        section="intro",
        replace="say this instead",
    )
    return {
        "attempt_id": attempt.id,
        "attempt_chat_id": attempt_chat.id,
        "message_id": message.id,
        "strength_id": strength.id,
        "hint_id": hint.id,
        "improvement_id": improvement.id,
        "highlight_id": highlight.id,
        "replacement_id": replacement.id,
    }


async def _refresh_all(conn):
    await refresh_attempt_strength(conn)
    await refresh_attempt_hint(conn)
    await refresh_attempt_improvement(conn)
    await refresh_attempt_highlight(conn)
    await refresh_attempt_replacement(conn)


async def _present(conn, ids):
    """Return which of the five analysis-family rows surface in their MVs."""
    present = set()
    for key, mv, col in (
        ("strength_id", "attempt_strength_mv", "strength_id"),
        ("hint_id", "attempt_hint_mv", "hint_id"),
        ("improvement_id", "attempt_improvement_mv", "improvement_id"),
        ("highlight_id", "attempt_highlight_mv", "highlight_id"),
        ("replacement_id", "attempt_replacement_mv", "replacement_id"),
    ):
        found = await conn.fetchval(
            f"SELECT 1 FROM {mv} WHERE {col} = $1", ids[key]
        )
        if found:
            present.add(key)
    return present


_FAMILY = {
    "strength_id",
    "hint_id",
    "improvement_id",
    "highlight_id",
    "replacement_id",
}


async def test_soft_deleted_message_excluded_from_all_mvs(
    conn, redis_client, profile_id
):
    ids = await _setup(conn, redis_client, profile_id)
    await _refresh_all(conn)

    # Sanity: all five surface while the chain is live.
    assert await _present(conn, ids) == _FAMILY

    # Soft-delete the joined message row (sm.active = false).
    await conn.execute(
        "UPDATE attempt_message_entry SET active = false WHERE id = $1",
        ids["message_id"],
    )
    await _refresh_all(conn)

    # Every dependent analysis-family row must drop out of its MV.
    assert await _present(conn, ids) == set()


async def test_soft_deleted_bridge_excluded_from_all_mvs(
    conn, redis_client, profile_id
):
    ids = await _setup(conn, redis_client, profile_id)
    await _refresh_all(conn)
    assert await _present(conn, ids) == _FAMILY

    # Soft-delete the joined chat-bridge row (ac.active = false).
    await conn.execute(
        """
        UPDATE attempt_chat_bridge_entry SET active = false
        WHERE attempt_id = $1 AND attempt_chat_id = $2
        """,
        ids["attempt_id"],
        ids["attempt_chat_id"],
    )
    await _refresh_all(conn)

    assert await _present(conn, ids) == set()
