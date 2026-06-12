"""Regression tests for the chat_create missing-attempt hardening.

Root cause: ``create_attempt_chat_impl`` (POST /attempt/chat_create) bridges the
new (or reused) attempt_chat into an attempt via ``create_attempt_chat_bridge``,
which carries hard FKs:

  - ``attempt_chat_bridge_entry.attempt_id → attempt_entry`` (``attempt_id`` —
    a required client UUID, fed on BOTH the main and short-circuit paths)
  - ``attempt_chat_bridge_entry.attempt_chat_id → attempt_chat_entry``
    (``previous_attempt_chat_id`` — fed on the short-circuit path)

Only ``chat_id`` was ever existence-checked (→ 404 "Chat template not found").
A stale/bogus ``attempt_id`` (or ``previous_attempt_chat_id``) therefore raised
an uncaught ``asyncpg.ForeignKeyViolationError`` that the route mapped to a raw
500. The impl now pre-validates both via the existing black-box getters
(``get_attempts`` / ``get_attempt_chats``) BEFORE either bridge insert and raises
a clean ``HTTPException(404)`` — mirroring the chat_id guard and the #299
chat_message fix.

These exercise the real impl against the testcontainers DB (pool + redis), the
same pattern as ``test_message_chat_fk.py``. The full chain is built through
black-box create tools — no raw SQL.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.attempt.chat_create import (
    CreateAttemptChatApiRequest,
    create_attempt_chat_impl,
)
from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt.refresh import refresh_attempt
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.chat.create import create_chat
from app.tools.entries.persona.create import create_persona
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _build_attempt_chain(pool, redis_client, profile):
    """Build a real session → persona → attempt → chat → attempt_chat chain and
    return ``(session_id, attempt_id, attempt_chat_id)``.

    Mirrors the production "advance to next chat" flow (see the route test
    ``test_chat_create_route_bridges_chat_into_attempt``): the attempt_chat is
    freshly created but NOT yet bridged into any attempt — it is therefore
    absent from ``attempt_chat_mv`` (which JOINs the bridge) but present in the
    write-back cache slot ``create_attempt_chat`` populated, so the impl's
    cache-hedged ``get_attempt_chats`` resolves it. The short-circuit then
    bridges it into the (single) attempt as a fresh pair — no duplicate bridge,
    no MV pollution. ``refresh_attempt`` puts the attempt in ``attempt_mv``.

    The attempt_chat carries ``session_id`` directly on the entry row, so the C1
    ownership gate (``enforce_attempt_access_by_attempt_chat``) resolves its
    owner via ``attempt_chat → session → profile`` regardless of bridge state —
    matching this real "advance to next chat" flow exactly.
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
        await refresh_attempt(conn)
    return session.id, attempt.id, attempt_chat.id


async def test_bogus_attempt_id_main_path_returns_404(
    pool, redis_client, profile_identity_factory
):
    """Main path (no previous_attempt_chat_id): a bogus attempt_id fails cleanly
    with 404 — NOT a raw 500 from the bridge FK violation."""
    profile = await profile_identity_factory()
    session, _attempt, _attempt_chat = await _build_attempt_chain(
        pool, redis_client, profile
    )

    request = CreateAttemptChatApiRequest(
        attempt_id=uuid4(),  # never inserted → FK target missing
        chat_id=uuid4(),
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_attempt_chat_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
            session_id=session,
            request=request,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Attempt not found."


async def test_bogus_attempt_id_short_circuit_path_returns_404(
    pool, redis_client, profile_identity_factory
):
    """Short-circuit path (previous_attempt_chat_id set): a bogus attempt_id
    fails cleanly with 404 — NOT a raw 500."""
    profile = await profile_identity_factory()
    session, _attempt, attempt_chat = await _build_attempt_chain(
        pool, redis_client, profile
    )

    request = CreateAttemptChatApiRequest(
        attempt_id=uuid4(),  # bogus
        chat_id=uuid4(),
        previous_attempt_chat_id=attempt_chat,  # valid
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_attempt_chat_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
            session_id=session,
            request=request,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Attempt not found."


async def test_bogus_previous_attempt_chat_id_returns_404(
    pool, redis_client, profile_identity_factory
):
    """A valid attempt_id but a bogus previous_attempt_chat_id fails cleanly with
    404 — NOT a raw 500 from the bridge's attempt_chat_id FK violation."""
    profile = await profile_identity_factory()
    session, attempt, _attempt_chat = await _build_attempt_chain(
        pool, redis_client, profile
    )

    request = CreateAttemptChatApiRequest(
        attempt_id=attempt,  # valid
        chat_id=uuid4(),
        previous_attempt_chat_id=uuid4(),  # never inserted → FK target missing
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_attempt_chat_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
            session_id=session,
            request=request,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Previous attempt chat not found."


async def test_valid_short_circuit_path_succeeds(
    pool, redis_client, profile_identity_factory
):
    """A valid attempt_id + valid previous_attempt_chat_id bridges the existing
    attempt_chat and returns 200 (unchanged short-circuit behavior).

    The owner reuses their OWN freshly-created, not-yet-bridged chat — the C1
    gate (``enforce_attempt_access_by_attempt_chat``) resolves the chat owner via
    its creating session to self and allows it, so the short-circuit succeeds and
    writes the first bridge."""
    profile = await profile_identity_factory()
    session, attempt, attempt_chat = await _build_attempt_chain(
        pool, redis_client, profile
    )

    request = CreateAttemptChatApiRequest(
        attempt_id=attempt,
        chat_id=uuid4(),
        previous_attempt_chat_id=attempt_chat,
    )
    result = await create_attempt_chat_impl(
        pool,
        redis_client,
        profile_id=profile.artifact_id,
        session_id=session,
        request=request,
    )

    assert result.attempt_chat_id == attempt_chat

    # The short-circuit actually bridged the reused attempt_chat into the attempt.
    async with pool.acquire() as conn:
        bridged = await conn.fetchval(
            "SELECT 1 FROM attempt_chat_bridge_entry "
            "WHERE attempt_id = $1 AND attempt_chat_id = $2",
            attempt,
            attempt_chat,
        )
    assert bridged == 1


# ── C1: attempt-ownership authorization ──────────────────────────────────────
#
# chat_create was the only attempt-side op taking caller-supplied ids that ran
# NO ``enforce_attempt_access_by_*`` guard, AND its reuse short-circuit returned
# BEFORE the permission check — so a non-owner could graft an attempt_chat (and,
# via ``previous_attempt_chat_id``, another user's conversation/grades) into a
# victim's attempt. These exercise the real impl + real ``check_attempt_access``
# against the testcontainers DB: a guest (role-level 0) attacker is denied on a
# victim's attempt (both the main and short-circuit paths), and grafting a
# non-owned ``previous_attempt_chat_id`` into one's own attempt is denied — with
# NO bridge row written. The owner remains allowed.


async def _bridge_count(pool, attempt_id):
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT count(*) FROM attempt_chat_bridge_entry WHERE attempt_id = $1",
            attempt_id,
        )


async def test_non_owner_denied_main_path(
    pool, redis_client, profile_identity_factory
):
    """A guest who does not own the attempt is denied (403) on the main path —
    no attempt_chat grafted into the victim's attempt."""
    owner = await profile_identity_factory()
    attacker = await profile_identity_factory(
        role=("guest", "Guest", "Guest role")
    )
    _owner_session, attempt, _ac = await _build_attempt_chain(
        pool, redis_client, owner
    )
    before = await _bridge_count(pool, attempt)

    # Attacker drives chat_create against the VICTIM's attempt from their own session.
    async with pool.acquire() as conn:
        atk_session = await create_session(
            conn, redis_client, profile_id=attacker.profile_resource_id
        )

    request = CreateAttemptChatApiRequest(attempt_id=attempt, chat_id=uuid4())
    with pytest.raises(HTTPException) as exc_info:
        await create_attempt_chat_impl(
            pool,
            redis_client,
            profile_id=attacker.artifact_id,
            session_id=atk_session.id,
            request=request,
        )

    assert exc_info.value.status_code == 403
    assert await _bridge_count(pool, attempt) == before  # nothing grafted


async def test_non_owner_denied_short_circuit_path(
    pool, redis_client, profile_identity_factory
):
    """The reuse short-circuit (previous_attempt_chat_id set) cannot bypass the
    ownership gate: a guest attacker is denied (403) BEFORE the early return —
    no bridge written."""
    owner = await profile_identity_factory()
    attacker = await profile_identity_factory(
        role=("guest", "Guest", "Guest role")
    )
    _owner_session, attempt, attempt_chat = await _build_attempt_chain(
        pool, redis_client, owner
    )
    before = await _bridge_count(pool, attempt)

    async with pool.acquire() as conn:
        atk_session = await create_session(
            conn, redis_client, profile_id=attacker.profile_resource_id
        )

    request = CreateAttemptChatApiRequest(
        attempt_id=attempt,
        chat_id=uuid4(),
        previous_attempt_chat_id=attempt_chat,  # valid, owned by the victim
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_attempt_chat_impl(
            pool,
            redis_client,
            profile_id=attacker.artifact_id,
            session_id=atk_session.id,
            request=request,
        )

    assert exc_info.value.status_code == 403
    assert await _bridge_count(pool, attempt) == before


async def test_grafting_non_owned_previous_chat_denied(
    pool, redis_client, profile_identity_factory
):
    """A caller owns the target attempt but supplies another user's
    previous_attempt_chat_id — denied (403), so a victim's conversation/grades
    cannot be pulled into the caller's own attempt."""
    # Caller is a guest (role-level 0): a student can only reach their OWN
    # chats, so grafting another user's chat is denied regardless of department.
    caller = await profile_identity_factory(role=("guest", "Guest", "Guest role"))
    victim = await profile_identity_factory()

    caller_session, caller_attempt, _ = await _build_attempt_chain(
        pool, redis_client, caller
    )
    # Victim's own chat the caller will try to graft — resolves to the victim
    # as owner via its creating session (a genuine cross-owner denial).
    _v_session, _v_attempt, victim_chat = await _build_attempt_chain(
        pool, redis_client, victim
    )
    before = await _bridge_count(pool, caller_attempt)

    request = CreateAttemptChatApiRequest(
        attempt_id=caller_attempt,  # caller owns this
        chat_id=uuid4(),
        previous_attempt_chat_id=victim_chat,  # NOT the caller's
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_attempt_chat_impl(
            pool,
            redis_client,
            profile_id=caller.artifact_id,
            session_id=caller_session,
            request=request,
        )

    assert exc_info.value.status_code == 403
    assert await _bridge_count(pool, caller_attempt) == before
