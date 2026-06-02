"""Shared test helpers — enforces correct patterns for test data isolation."""

from dataclasses import dataclass
from uuid import UUID, uuid4


def unique_tag() -> str:
    """Short unique string for test data isolation (name suffixes, search tags)."""
    return uuid4().hex[:8]


def nonexistent_id() -> UUID:
    """UUID guaranteed not to exist in the database — for 'returns empty' tests."""
    return uuid4()


@dataclass
class AttemptChatGraph:
    """IDs produced by :func:`create_attempt_chat_graph`."""

    session_id: UUID
    group_id: UUID
    run_id: UUID
    persona_id: UUID
    attempt_id: UUID
    chat_id: UUID
    call_id: UUID
    attempt_chat_id: UUID


async def create_attempt_chat_graph(
    conn,
    redis,
    profile_id,
    **attempt_chat_overrides,
) -> AttemptChatGraph:
    """Build the full session → group → run → call → persona → attempt → chat
    → attempt_chat → bridge chain via black-box tools and return the chain IDs.

    ``attempt_chat`` is session+chat-linked: it takes ``session_id`` (the
    sessions_entry the chat belongs to) and ``chat_id`` (the base chat). Extra
    keyword args are forwarded to ``create_attempt_chat``.
    """
    from app.tools.entries.attempt.create import create_attempt
    from app.tools.entries.attempt_chat.create import create_attempt_chat
    from app.tools.entries.attempt_chat_bridge.create import (
        create_attempt_chat_bridge,
    )
    from app.tools.entries.calls.create import create_call
    from app.tools.entries.chat.create import create_chat
    from app.tools.entries.groups.create import create_group
    from app.tools.entries.persona.create import create_persona
    from app.tools.entries.runs.create import create_run
    from app.tools.entries.sessions.create import create_session

    session = await create_session(conn, redis, profile_id=profile_id)
    group = await create_group(
        conn, redis, session_id=session.id, artifact_type="persona"
    )
    run = await create_run(conn, redis, group_id=group.id, session_id=session.id)
    persona = await create_persona(conn, redis)
    attempt = await create_attempt(
        conn,
        redis,
        session_id=session.id,
        user_persona_id=persona.id,
        profiles_id=profile_id,
    )
    chat = await create_chat(conn, redis, session_id=session.id)
    call = await create_call(conn, redis, run_id=run.id, session_id=session.id)
    attempt_chat = await create_attempt_chat(
        conn,
        redis,
        session_id=session.id,
        chat_id=chat.id,
        **attempt_chat_overrides,
    )
    # Bridge is required for MV visibility.
    await create_attempt_chat_bridge(
        conn,
        redis,
        attempt_id=attempt.id,
        attempt_chat_id=attempt_chat.id,
        session_id=session.id,
    )
    return AttemptChatGraph(
        session_id=session.id,
        group_id=group.id,
        run_id=run.id,
        persona_id=persona.id,
        attempt_id=attempt.id,
        chat_id=chat.id,
        call_id=call.id,
        attempt_chat_id=attempt_chat.id,
    )
