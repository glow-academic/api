"""Regression tests for the chat_message missing-chat hardening.

Root cause (verified on v1.1.0): the message insert carries a hard FK
``attempt_message_entry.chat_id → attempt_chat_entry``. A stale/bogus
``chat_id`` made ``create_attempt_message`` raise an uncaught
``asyncpg.ForeignKeyViolationError`` which bubbled out of the route as a raw
500 — the route only maps ``ValueError → 400``. The impl now pre-validates the
chat via the existing black-box getter (``get_attempt_chats``) and raises a
clean ``HTTPException(404)`` (same shape as its other 400/401 guards), which
propagates cleanly through ``run_artifact_operation_with_audit``.

These exercise the real impl against the testcontainers DB (pool + redis), the
same pattern as the benchmark-export integration tests. The full chain is built
through black-box create tools — no raw SQL.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.attempt.message import attempt_message_internal_impl
from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_chat.refresh import refresh_attempt_chat
from app.tools.entries.attempt_chat_bridge.create import create_attempt_chat_bridge
from app.tools.entries.chat.create import create_chat
from app.tools.entries.persona.create import create_persona
from app.tools.entries.sessions.create import create_session
from app.tools.resources.audios.create import create_audio_resource

pytestmark = pytest.mark.asyncio


async def _build_chat_chain(pool, redis_client, profile):
    """Build a real session → persona → attempt → chat → attempt_chat → bridge
    chain on the pool and return ``(session_id, attempt_chat_id, persona_id)``.

    Writes commit on the autocommit pool connection so the impl's separate
    pool connection (and the message-insert FK) sees the chat.
    """
    async with pool.acquire() as conn:
        session = await create_session(
            conn, redis_client, profile_id=profile.profile_resource_id
        )
        persona = await create_persona(conn, redis_client)
        attempt = await create_attempt(
            conn,
            redis_client,
            session_id=session.id,
            user_persona_id=persona.id,
            profiles_id=profile.profile_resource_id,
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
        # The bridge create invalidates the attempt_chat write-back cache slot
        # (so the next read hydrates attempt_id from the MV). Refresh the MV so
        # the chat resolves via get_attempt_chats — mirrors production, where a
        # real chat is always present in attempt_chat_mv.
        await refresh_attempt_chat(conn)
    return session.id, attempt_chat.id, persona.id


async def test_nonexistent_chat_id_returns_404(
    pool, redis_client, profile_identity_factory
):
    """A bogus/stale chat_id fails cleanly with 404 — NOT a raw 500."""
    profile = await profile_identity_factory()
    session, _attempt_chat, persona = await _build_chat_chain(
        pool, redis_client, profile
    )

    with pytest.raises(HTTPException) as exc_info:
        await attempt_message_internal_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
            session_id=session,
            chat_id=uuid4(),  # never inserted → FK target missing
            text="hello",
            persona_id=persona,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "chat not found"


async def test_valid_chat_id_succeeds(
    pool, redis_client, profile_identity_factory
):
    """An existing chat still posts a message (unchanged 200 path)."""
    profile = await profile_identity_factory()
    session, attempt_chat, persona = await _build_chat_chain(
        pool, redis_client, profile
    )

    result = await attempt_message_internal_impl(
        pool,
        redis_client,
        profile_id=profile.artifact_id,
        session_id=session,
        chat_id=attempt_chat,
        text="hello",
        persona_id=persona,
    )

    assert result.success is True
    assert result.message_id is not None
    assert result.content_ids


async def test_missing_chat_id_returns_400(pool, redis_client):
    """The pre-existing chat_id-required guard is unchanged (400)."""
    with pytest.raises(HTTPException) as exc_info:
        await attempt_message_internal_impl(
            pool,
            redis_client,
            profile_id=uuid4(),
            chat_id=None,
            text="hello",
            persona_id=uuid4(),
        )

    assert exc_info.value.status_code == 400
    assert "chat_id is required" in exc_info.value.detail


async def test_missing_text_returns_400(pool, redis_client):
    """The pre-existing text-required guard is unchanged (400)."""
    with pytest.raises(HTTPException) as exc_info:
        await attempt_message_internal_impl(
            pool,
            redis_client,
            profile_id=uuid4(),
            chat_id=uuid4(),
            text=None,
            persona_id=uuid4(),
        )

    assert exc_info.value.status_code == 400
    assert "text or contents is required" in exc_info.value.detail


async def test_missing_persona_raises_value_error(
    pool, redis_client, profile_identity_factory
):
    """The pre-existing persona-required guard is unchanged (ValueError → 400).

    Needs a real chat so the new 404 pre-validate passes and execution reaches
    the content-creation loop where the persona guard lives.
    """
    profile = await profile_identity_factory()
    session, attempt_chat, _persona = await _build_chat_chain(
        pool, redis_client, profile
    )

    with pytest.raises(ValueError, match="persona_id is required"):
        await attempt_message_internal_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
            session_id=session,
            chat_id=attempt_chat,
            text="hello",
            persona_id=None,
        )


# --- #299 follow-up: the two OTHER client-supplied FKs + write atomicity. ----
# #299 only closed chat_id. POST /attempt/chat_message also accepts
# ``parent_message_id`` (FK attempt_message_tree_entry.parent_id →
# attempt_message_entry) and ``audios_id`` (FK attempt_audio_entry.audios_id →
# audios_resource). A stale/bogus value for either still raised an uncaught
# asyncpg.ForeignKeyViolationError → raw 500, AND — because the writes ran on
# the bare autocommit pool connection — left a DANGLING message row. These
# exercise the pre-validate (clean 404) + the new wrapping transaction.


async def _message_count(pool, chat_id):
    """Count attempt_message_entry rows for a chat (raw — asserting DB state,
    not building fixtures; the MV-backed getters can't see uncommitted/
    unrefreshed rows, so a direct entry-table read is the only way to prove a
    rollback left nothing behind)."""
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT count(*) FROM attempt_message_entry WHERE chat_id = $1",
            chat_id,
        )


async def test_nonexistent_parent_message_id_returns_404(
    pool, redis_client, profile_identity_factory
):
    """A bogus/stale parent_message_id fails cleanly with 404 — NOT a raw 500."""
    profile = await profile_identity_factory()
    session, attempt_chat, persona = await _build_chat_chain(
        pool, redis_client, profile
    )

    with pytest.raises(HTTPException) as exc_info:
        await attempt_message_internal_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
            session_id=session,
            chat_id=attempt_chat,
            text="hello",
            persona_id=persona,
            parent_message_id=uuid4(),  # never inserted → tree FK target missing
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "parent message not found"


async def test_nonexistent_audios_id_returns_404(
    pool, redis_client, profile_identity_factory
):
    """A bogus/stale audios_id fails cleanly with 404 — NOT a raw 500."""
    profile = await profile_identity_factory()
    session, attempt_chat, persona = await _build_chat_chain(
        pool, redis_client, profile
    )

    with pytest.raises(HTTPException) as exc_info:
        await attempt_message_internal_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
            session_id=session,
            chat_id=attempt_chat,
            text="hello",
            persona_id=persona,
            audios_id=uuid4(),  # never inserted → audio FK target missing
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "audio not found"


async def test_valid_audios_id_succeeds(
    pool, redis_client, profile_identity_factory
):
    """A real audios_resource attaches and the message still posts (200)."""
    profile = await profile_identity_factory()
    session, attempt_chat, persona = await _build_chat_chain(
        pool, redis_client, profile
    )
    async with pool.acquire() as conn:
        audio = await create_audio_resource(
            conn, "mic recording", "transcribed user audio", redis_client
        )

    result = await attempt_message_internal_impl(
        pool,
        redis_client,
        profile_id=profile.artifact_id,
        session_id=session,
        chat_id=attempt_chat,
        text="hello",
        persona_id=persona,
        audios_id=audio.id,
    )

    assert result.success is True
    assert result.message_id is not None


async def test_failed_insert_rolls_back_no_dangling_message(
    pool, redis_client, profile_identity_factory
):
    """A downstream failure (the persona guard, raised AFTER the message row is
    created) rolls the whole write back — no dangling attempt_message_entry.

    Pre-fix the message committed on the autocommit pool connection before the
    content loop ran, so the post-failure count was 1. The wrapping
    ``conn.transaction()`` makes it 0.
    """
    profile = await profile_identity_factory()
    session, attempt_chat, _persona = await _build_chat_chain(
        pool, redis_client, profile
    )

    assert await _message_count(pool, attempt_chat) == 0

    with pytest.raises(ValueError, match="persona_id is required"):
        await attempt_message_internal_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
            session_id=session,
            chat_id=attempt_chat,
            text="hello",
            persona_id=None,  # trips the guard AFTER create_attempt_message
        )

    # Transaction rolled back → the message row created before the guard fired
    # must be gone. (Pre-fix this asserted 1 — a dangling message.)
    assert await _message_count(pool, attempt_chat) == 0
