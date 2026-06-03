"""Cache-coherence regression tests (#105 class) for attempt_message.

attempt_message_mv derives ``type`` from the message's first
attempt_content_entry and ``audios_id`` from the latest attempt_audio_entry.
Creating those child rows for an existing message must invalidate the
parent attempt_message write-back cache (keyed by message_id), otherwise a
reader served from the stale cache row sees ``type``/``audios_id`` as None
even after the MV has refreshed — read-after-write staleness.

These mutate, then read, and assert the read is fresh (not stale). They take
``conn``/``redis_client`` as explicit params and reuse black-box create/search
tools only (no raw SQL).
"""

import pytest

from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_audio.create import create_attempt_audio
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_chat_bridge.create import (
    create_attempt_chat_bridge,
)
from app.tools.entries.attempt_content.create import create_attempt_content
from app.tools.entries.attempt_message.create import create_attempt_message
from app.tools.entries.attempt_message.get import get_attempt_messages
from app.tools.entries.attempt_message.refresh import refresh_attempt_message
from app.tools.entries.attempt_message.search import search_attempt_messages
from app.tools.entries.calls.create import create_call
from app.tools.entries.chat.create import create_chat
from app.tools.entries.groups.create import create_group
from app.tools.entries.persona.create import create_persona
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.resources.audios.create import create_audio_resource
from tests.helpers import unique_tag

pytestmark = pytest.mark.asyncio


async def _message(conn, redis, profile_id):
    """Black-box chain → an attempt_message whose write-back cache is now warm.

    Returns (message_id, attempt_chat_id, session_id, persona_id).
    """
    session = await create_session(conn, redis, profile_id=profile_id)
    group = await create_group(
        conn, redis, session_id=session.id, artifact_type="persona"
    )
    run = await create_run(conn, redis, group_id=group.id, session_id=session.id)
    await create_call(conn, redis, run_id=run.id, session_id=session.id)
    persona = await create_persona(conn, redis)
    attempt = await create_attempt(
        conn,
        redis,
        session_id=session.id,
        user_persona_id=persona.id,
        profiles_id=profile_id,
    )
    chat = await create_chat(conn, redis, session_id=session.id)
    attempt_chat = await create_attempt_chat(
        conn, redis, session_id=session.id, chat_id=chat.id
    )
    await create_attempt_chat_bridge(
        conn,
        redis,
        attempt_id=attempt.id,
        attempt_chat_id=attempt_chat.id,
        session_id=session.id,
    )
    msg = await create_attempt_message(
        conn, redis, chat_id=attempt_chat.id, session_id=session.id
    )
    return msg.id, attempt_chat.id, session.id, persona.id


async def test_content_create_busts_stale_message_type_cache(
    conn, redis_client, profile_id
):
    """Attaching content to a message must not leave a stale ``type=None``
    in the attempt_message cache (get-by-id path)."""
    message_id, _chat_id, session_id, _persona_id = await _message(
        conn, redis_client, profile_id
    )
    # A distinct responder persona so the MV derives type='response'.
    responder = await create_persona(conn, redis_client)

    await create_attempt_content(
        conn,
        redis_client,
        message_id=message_id,
        session_id=session_id,
        content="hello",
        persona_id=responder.id,
    )
    await refresh_attempt_message(conn)

    items = await get_attempt_messages(conn, [message_id], redis_client)
    assert len(items) == 1
    # Pre-fix: cache row (written at message-create with type=None) masks the
    # MV → type is stale None. Post-fix: invalidated → MV type surfaces.
    assert items[0].type is not None


async def test_audio_create_busts_stale_message_audios_cache(
    conn, redis_client, profile_id
):
    """Attaching audio to a message must not leave a stale ``audios_id=None``
    in the attempt_message cache (search path)."""
    message_id, chat_id, session_id, _persona_id = await _message(
        conn, redis_client, profile_id
    )
    audio = await create_audio_resource(
        conn,
        name=f"clip-{unique_tag()}",
        description="regression",
        redis=redis_client,
    )

    await create_attempt_audio(
        conn,
        redis_client,
        message_id=message_id,
        audios_id=audio.id,
        session_id=session_id,
    )
    await refresh_attempt_message(conn)

    items, _total = await search_attempt_messages(
        conn, redis_client, chat_ids=[chat_id]
    )
    matched = [m for m in items if m.message_id == message_id]
    assert matched, "message should be returned by chat-scoped search"
    # Pre-fix: stale cache row (audios_id=None) wins the hedged merge over the
    # MV row for this message_id. Post-fix: invalidated → MV audios_id surfaces.
    assert matched[0].audios_id == audio.id
