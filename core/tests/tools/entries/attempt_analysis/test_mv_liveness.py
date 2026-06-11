"""D1 regression: attempt_analysis_mv must exclude soft-deleted rows.

attempt_analysis_mv read straight from attempt_analysis_entry with no
`WHERE active = true`, so soft-deleted / dormant rows (active = false) leaked
into analysis reads. Every sibling MV fronting a soft-deletable *_entry table
carries the liveness filter; this MV omitted it. The fix adds
`WHERE (active = true)` to the MV body (and the migration recreates it).

Modular: builds a real grade via the standard create chain, then writes one
active + one soft analysis entry, refreshes the MV, and asserts only the active
row surfaces — both from the MV directly and via the bypass-MV inline
definition path (search_attempt_analyses bypass_mv=True), which also must carry
the filter.
"""

import pytest

from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_analysis.create import create_attempt_analysis
from app.tools.entries.attempt_analysis.refresh import refresh_attempt_analysis
from app.tools.entries.attempt_analysis.search import search_attempt_analyses
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_chat_bridge.create import (
    create_attempt_chat_bridge,
)
from app.tools.entries.attempt_grade.create import create_attempt_grade
from app.tools.entries.chat.create import create_chat
from app.tools.entries.groups.create import create_group
from app.tools.entries.persona.create import create_persona
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _make_grade(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(
        conn, redis_client, session_id=session.id, artifact_type="persona"
    )
    run = await create_run(
        conn, redis_client, group_id=group.id, session_id=session.id
    )
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
    grade = await create_attempt_grade(
        conn,
        redis_client,
        chat_id=attempt_chat.id,
        session_id=session.id,
        time_taken=120,
        passed=True,
        score=85,
    )
    return grade, session


async def test_mv_excludes_soft_deleted_analysis(conn, redis_client, profile_id):
    grade, session = await _make_grade(conn, redis_client, profile_id)

    active = await create_attempt_analysis(
        conn, redis_client, grade_id=grade.id, session_id=session.id,
        content="live analysis",
    )
    dormant = await create_attempt_analysis(
        conn, redis_client, grade_id=grade.id, session_id=session.id,
        content="soft-deleted analysis", soft=True,
    )

    await refresh_attempt_analysis(conn)

    # Query the MV directly: only the active row may appear.
    mv_ids = {
        r["analysis_id"]
        for r in await conn.fetch(
            "SELECT analysis_id FROM attempt_analysis_mv WHERE grade_id = $1",
            grade.id,
        )
    }
    assert active.id in mv_ids
    assert dormant.id not in mv_ids


async def test_bypass_mv_inline_definition_also_excludes_soft_deleted(
    conn, redis_client, profile_id
):
    """The bypass-MV path inlines the MV definition, so it must filter too."""
    grade, session = await _make_grade(conn, redis_client, profile_id)

    active = await create_attempt_analysis(
        conn, redis_client, grade_id=grade.id, session_id=session.id,
        content="live analysis",
    )
    dormant = await create_attempt_analysis(
        conn, redis_client, grade_id=grade.id, session_id=session.id,
        content="soft-deleted analysis", soft=True,
    )

    # bypass_cache so the write-back of the soft row can't mask the filter.
    results = await search_attempt_analyses(
        conn, redis_client, grade_ids=[grade.id],
        bypass_mv=True, bypass_cache=True,
    )
    ids = {r.analysis_id for r in results}
    assert active.id in ids
    assert dormant.id not in ids
