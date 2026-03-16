"""Tests for trivial attempt event translators — EmitFn pattern.

Each impl is a simple pass-through: receive data → resolve context → emit event.
Uses recording_emit() to capture events.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest
import pytest_asyncio
from tests.helpers import nonexistent_id

import app.infra.globals as globals_mod
import app.infra.websocket.audio_lifecycle as audio_lifecycle
from app.infra.websocket.attempt_events_impl import (
    attempt_next_impl,
    audio_delta_impl,
    audio_error_impl,
    audio_response_cancelled_impl,
    audio_session_start_impl,
    audio_speech_delta_impl,
    audio_speech_start_impl,
    audio_stop_impl,
    user_progress_impl,
    user_start_impl,
)
from app.infra.websocket.attempt_events_impl import (
    attempt_proceed_impl as _attempt_proceed_impl,
)
from app.infra.websocket.attempt_events_impl import (
    attempt_start_impl as _attempt_start_impl,
)
from app.infra.websocket.attempt_events_impl import (
    emit_chat_generate_impl as _emit_chat_generate_impl,
)
from app.infra.websocket.attempt_events_impl import (
    speech_complete_impl as _speech_complete_impl,
)
from app.infra.websocket.attempt_events_impl import (
    user_complete_impl as _user_complete_impl,
)
from app.infra.websocket.session_store import (
    _session_store,
    get_session_by_group_id,
    remove_session,
)
from app.infra.websocket.session_store import create_session as create_audio_session
from app.infra.websocket.set_socket_owner import set_socket_owner
from app.infra.websocket.socket_event import recording_emit
from app.infra.websocket.test_events_impl import (
    _extract_grade_feedback,
    _extract_grade_passed,
    _extract_grade_score,
    _find_next_run_id,
)
from app.infra.websocket.test_events_impl import (
    test_error_impl as _test_error_impl,
)
from app.infra.websocket.test_events_impl import (
    test_grade_complete_impl as _test_grade_complete_impl,
)
from app.infra.websocket.test_events_impl import (
    test_group_impl as _test_group_impl,
)
from app.infra.websocket.test_events_impl import (
    test_next_impl as _test_next_impl,
)
from app.infra.websocket.test_events_impl import (
    test_proceed_impl as _test_proceed_impl,
)
from app.infra.websocket.test_events_impl import (
    test_progress_impl as _test_progress_impl,
)
from app.infra.websocket.test_events_impl import (
    test_run_done_impl as _test_run_done_impl,
)
from app.infra.websocket.test_events_impl import (
    test_run_impl as _test_run_impl,
)
from app.infra.websocket.test_events_impl import (
    test_start_impl as _test_start_impl,
)
from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt.get import get_attempts
from app.tools.entries.attempt.refresh import refresh_attempt
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_chat.search import search_attempt_chats
from app.tools.entries.attempt_chat_bridge.create import (
    create_attempt_chat_bridge,
)
from app.tools.entries.attempt_chat_bridge.search import (
    search_attempt_chat_bridges,
)
from app.tools.entries.attempt_chat_completion.search import (
    search_attempt_chat_completions,
)
from app.tools.entries.attempt_content.search import search_attempt_contents
from app.tools.entries.attempt_message.create import create_attempt_message
from app.tools.entries.attempt_message.search import search_attempt_messages
from app.tools.entries.attempt_message_completion.create import (
    create_attempt_message_completion,
)
from app.tools.entries.attempt_message_completion.search import (
    search_attempt_message_completions,
)
from app.tools.entries.attempt_practice.create import (
    create_attempt_practice,
)
from app.tools.entries.benchmark.create import create_benchmark
from app.tools.entries.calls.create import create_call
from app.tools.entries.chat.create import create_chat
from app.tools.entries.chat.refresh import refresh_chat
from app.tools.entries.groups.create import create_group
from app.tools.entries.groups.get import get_groups
from app.tools.entries.messages.create import create_message
from app.tools.entries.messages.get import get_message
from app.tools.entries.messages.search import search_messages
from app.tools.entries.persona.create import create_persona
from app.tools.entries.practice.create import create_practice
from app.tools.entries.practice.refresh import refresh_practice
from app.tools.entries.practice_chat.create import create_practice_chat
from app.tools.entries.practice_chat.refresh import refresh_practice_chat
from app.tools.entries.runs.create import create_run
from app.tools.entries.runs.get import get_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.test.create import create_test
from app.tools.entries.test.refresh import refresh_test
from app.tools.entries.test_grade.create import create_test_grade
from app.tools.entries.test_invocation.create import create_test_invocation
from app.tools.entries.test_invocation.refresh import refresh_test_invocation
from app.tools.entries.test_invocation.search import (
    search_test_invocation_entries_internal,
)
from app.tools.entries.test_invocation_completion.search import (
    search_test_invocation_completions,
)
from app.tools.entries.tokens.refresh import refresh_tokens
from app.tools.entries.tokens.search import search_tokens
from app.tools.entries.uploads.get import get_upload
from app.tools.resources.departments.create import create_department
from app.tools.resources.personas.create import (
    create_persona as create_persona_resource,
)
from app.tools.resources.profile_personas.create import create_profile_persona
from app.tools.resources.profiles.create import create_profile
from app.tools.resources.simulations.create import create_simulation

_P = "app.infra.websocket.attempt_events_impl"


@pytest_asyncio.fixture
async def audio_session_factory(redis_client):
    """Create real audio session-store state plus Redis socket mappings."""
    previous_redis = globals_mod.redis_client
    globals_mod.redis_client = redis_client
    _session_store.clear()
    globals_mod.get_socket_owner_dict().clear()
    tracked_group_ids: list[str] = []
    tracked_profile_ids: list[str] = []
    tracked_sids: list[str] = []

    async def _create(
        *,
        sid: str = "s1",
        chat_id: str = "c1",
        run_id: str = "r1",
        group_id: str = "g1",
        profile_id: str | None = None,
        session_id: str | None = None,
    ):
        session = create_audio_session(
            sid=sid,
            chat_id=chat_id,
            run_id=run_id,
            group_id=group_id,
        )
        tracked_group_ids.append(group_id)

        if profile_id is not None:
            await set_socket_owner(profile_id, sid)
            tracked_profile_ids.append(profile_id)

        if session_id is not None:
            await redis_client.set(f"socket_session:{sid}", session_id)
            tracked_sids.append(sid)

        return session

    try:
        yield _create
    finally:
        for group_id in tracked_group_ids:
            remove_session(group_id)
        for profile_id in tracked_profile_ids:
            await redis_client.delete(
                f"socket_owner:{profile_id}",
            )
        for sid in tracked_sids:
            await redis_client.delete(
                f"socket_session:{sid}", f"socket_to_profile:{sid}"
            )
        _session_store.clear()
        globals_mod.get_socket_owner_dict().clear()
        globals_mod.redis_client = previous_redis


@pytest_asyncio.fixture
async def attempt_chat_factory(pool, redis_client):
    """Create a minimal real attempt chat graph for attempt message tests."""

    async def _create():
        async with pool.acquire() as conn:
            profile = await create_profile(conn, redis_client)
            session = await create_session(conn, profile_id=profile.id)
            group = await create_group(conn, session_id=session.id)
            run = await create_run(conn, group_id=group.id, session_id=session.id)
            call = await create_call(conn, run_id=run.id, session_id=session.id)
            persona = await create_persona(conn, session_id=session.id)
            attempt = await create_attempt(
                conn,
                call_id=call.id,
                user_persona_id=persona.id,
                profiles_id=profile.id,
            )
            chat = await create_chat(conn, session_id=session.id)
            call2 = await create_call(conn, run_id=run.id, session_id=session.id)
            attempt_chat = await create_attempt_chat(
                conn,
                call_id=call2.id,
                group_id=group.id,
                chat_id=chat.id,
            )
            await create_attempt_chat_bridge(
                conn,
                attempt_id=attempt.id,
                attempt_chat_id=attempt_chat.id,
                session_id=session.id,
            )
        return SimpleNamespace(
            profile=profile,
            session=session,
            group=group,
            run=run,
            attempt=attempt,
            attempt_chat=attempt_chat,
        )

    return _create


# ═══════════════════════════════════════════════════════════════════════════
# user_progress_impl
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestUserProgressImpl:
    async def test_no_sid_emits_nothing(self):
        emit, events = recording_emit()
        await user_progress_impl({"sid": "", "chat_id": "c1"}, emit=emit)
        assert events == []

    async def test_no_chat_id_emits_nothing(self):
        emit, events = recording_emit()
        await user_progress_impl({"sid": "s1", "chat_id": ""}, emit=emit)
        assert events == []

    async def test_emits_user_progress(self):
        emit, events = recording_emit()
        await user_progress_impl(
            {"sid": "s1", "chat_id": "c1", "transcript": "hello", "item_id": "i1"},
            emit=emit,
        )
        assert len(events) == 1
        assert events[0].event == "attempt_user_progress"
        assert events[0].data["transcript"] == "hello"
        assert events[0].data["chat_id"] == "c1"


# ═══════════════════════════════════════════════════════════════════════════
# audio_session_start_impl
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestAudioSessionStartImpl:
    async def test_no_sid_emits_nothing(self):
        emit, events = recording_emit()
        await audio_session_start_impl({"group_id": "g1"}, emit=emit)
        assert events == []

    async def test_no_group_id_emits_nothing(self):
        emit, events = recording_emit()
        await audio_session_start_impl({"sid": "s1"}, emit=emit)
        assert events == []

    async def test_emits_audio_ready_with_session(self, audio_session_factory):
        emit, events = recording_emit()
        await audio_session_factory(chat_id="chat-1")
        await audio_session_start_impl({"sid": "s1", "group_id": "g1"}, emit=emit)
        assert len(events) == 1
        assert events[0].event == "attempt_audio_ready"
        assert events[0].data["chat_id"] == "chat-1"

    async def test_no_session_uses_group_id_as_chat_id(self):
        emit, events = recording_emit()
        await audio_session_start_impl({"sid": "s1", "group_id": "g1"}, emit=emit)
        assert events[0].data["chat_id"] == "g1"


# ═══════════════════════════════════════════════════════════════════════════
# audio_delta_impl
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestAudioDeltaImpl:
    async def test_no_group_id_emits_nothing(self):
        emit, events = recording_emit()
        await audio_delta_impl({}, emit=emit)
        assert events == []

    async def test_no_session_emits_nothing(self):
        emit, events = recording_emit()
        await audio_delta_impl({"group_id": "g1", "audio": b"data"}, emit=emit)
        assert events == []

    async def test_no_audio_data_emits_nothing(self, audio_session_factory):
        emit, events = recording_emit()
        await audio_session_factory()
        await audio_delta_impl({"group_id": "g1"}, emit=emit)
        assert events == []

    async def test_emits_assistant_progress(self, audio_session_factory):
        emit, events = recording_emit()
        await audio_session_factory()
        await audio_delta_impl({"group_id": "g1", "audio": b"chunk"}, emit=emit)
        assert len(events) == 1
        assert events[0].event == "attempt_assistant_progress"
        assert events[0].data["content_type"] == "audio"


# ═══════════════════════════════════════════════════════════════════════════
# audio_speech_start_impl
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestAudioSpeechStartImpl:
    async def test_no_group_id_emits_nothing(self):
        emit, events = recording_emit()
        await audio_speech_start_impl({}, emit=emit)
        assert events == []

    async def test_no_session_emits_nothing(self):
        emit, events = recording_emit()
        await audio_speech_start_impl({"group_id": "g1", "item_id": "i1"}, emit=emit)
        assert events == []

    async def test_no_item_id_emits_nothing(self, audio_session_factory):
        emit, events = recording_emit()
        await audio_session_factory()
        await audio_speech_start_impl({"group_id": "g1"}, emit=emit)
        assert events == []

    async def test_emits_user_received_start(self, audio_session_factory):
        emit, events = recording_emit()
        await audio_session_factory(
            profile_id="prof-1",
            session_id="sess-1",
        )
        await audio_speech_start_impl({"group_id": "g1", "item_id": "i1"}, emit=emit)
        assert len(events) == 1
        assert events[0].event == "attempt_user_received_start"
        assert events[0].data["profile_id"] == "prof-1"
        assert events[0].data["session_id"] == "sess-1"
        assert events[0].data["item_id"] == "i1"


# ═══════════════════════════════════════════════════════════════════════════
# audio_speech_delta_impl
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestAudioSpeechDeltaImpl:
    async def test_no_group_id_emits_nothing(self):
        emit, events = recording_emit()
        await audio_speech_delta_impl({}, emit=emit)
        assert events == []

    async def test_no_session_emits_nothing(self):
        emit, events = recording_emit()
        await audio_speech_delta_impl({"group_id": "g1", "item_id": "i1"}, emit=emit)
        assert events == []

    async def test_no_item_id_emits_nothing(self, audio_session_factory):
        emit, events = recording_emit()
        await audio_session_factory()
        await audio_speech_delta_impl({"group_id": "g1"}, emit=emit)
        assert events == []

    async def test_emits_user_received_progress(self, audio_session_factory):
        emit, events = recording_emit()
        await audio_session_factory()
        await audio_speech_delta_impl(
            {"group_id": "g1", "item_id": "i1", "transcript": "hi"},
            emit=emit,
        )
        assert len(events) == 1
        assert events[0].event == "attempt_user_received_progress"
        assert events[0].data["transcript"] == "hi"


# ═══════════════════════════════════════════════════════════════════════════
# audio_error_impl
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestAudioErrorImpl:
    async def test_no_group_id_emits_nothing(self):
        emit, events = recording_emit()
        await audio_error_impl({}, emit=emit)
        assert events == []

    async def test_no_session_emits_nothing(self):
        emit, events = recording_emit()
        await audio_error_impl({"group_id": "g1"}, emit=emit)
        assert events == []

    async def test_emits_attempt_error(self, audio_session_factory):
        emit, events = recording_emit()
        await audio_session_factory()
        await audio_error_impl(
            {"group_id": "g1", "error_message": "mic broke"}, emit=emit
        )
        assert len(events) == 1
        assert events[0].event == "attempt_error"
        assert events[0].data["error_type"] == "audio"
        assert events[0].data["message"] == "mic broke"

    async def test_default_error_message(self, audio_session_factory):
        emit, events = recording_emit()
        await audio_session_factory()
        await audio_error_impl({"group_id": "g1"}, emit=emit)
        assert events[0].data["message"] == "Unknown audio error"


# ═══════════════════════════════════════════════════════════════════════════
# attempt_next_impl
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestAttemptNextImpl:
    async def test_no_sid_emits_nothing(self):
        emit, events = recording_emit()
        await attempt_next_impl(
            {"sid": ""},
            emit=emit,
            attempt_id=str(nonexistent_id()),
            draft_id=None,
            profile_id=str(nonexistent_id()),
            session_id=str(nonexistent_id()),
            pool=object(),
        )
        assert events == []

    async def test_emits_attempt_proceed(self):
        emit, events = recording_emit()
        group_id = nonexistent_id()

        async def fake_identity(*args, **kwargs):
            return SimpleNamespace(group_id=group_id)

        await attempt_next_impl(
            {"sid": "s1"},
            emit=emit,
            attempt_id=str(nonexistent_id()),
            draft_id="d1",
            profile_id=str(nonexistent_id()),
            session_id=str(nonexistent_id()),
            pool=object(),
            resolve_profile_identity_fn=fake_identity,
        )
        assert len(events) == 1
        assert events[0].event == "attempt_proceed"
        assert events[0].data["force_proceed"] is True
        assert events[0].data["group_id"] == str(group_id)
        assert events[0].data["draft_id"] == "d1"

    async def test_error_emits_attempt_error(self):
        """If emit raises during proceed, emits attempt_error instead."""
        call_count = 0
        group_id = nonexistent_id()

        async def failing_emit(events_list):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("bus down")
            # Second call (error emit) succeeds — capture it
            captured.extend(events_list)

        async def fake_identity(*args, **kwargs):
            return SimpleNamespace(group_id=group_id)

        captured = []
        await attempt_next_impl(
            {"sid": "s1"},
            emit=failing_emit,
            attempt_id=str(nonexistent_id()),
            draft_id=None,
            profile_id=str(nonexistent_id()),
            session_id=str(nonexistent_id()),
            pool=object(),
            resolve_profile_identity_fn=fake_identity,
        )
        assert len(captured) == 1
        assert captured[0].event == "attempt_error"
        assert "bus down" in captured[0].data["message"]


# ═══════════════════════════════════════════════════════════════════════════
# user_start_impl
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestUserStartImpl:
    async def test_no_sid_emits_nothing(self):
        emit, events = recording_emit()
        await user_start_impl(
            {"sid": "", "chat_id": "c1", "run_id": "r1"},
            emit=emit,
            pool=object(),
        )
        assert events == []

    async def test_no_chat_id_emits_nothing(self):
        emit, events = recording_emit()
        await user_start_impl(
            {"sid": "s1", "chat_id": "", "run_id": "r1"},
            emit=emit,
            pool=object(),
        )
        assert events == []

    async def test_no_run_id_emits_nothing(self):
        emit, events = recording_emit()
        await user_start_impl(
            {"sid": "s1", "chat_id": "c1", "run_id": ""},
            emit=emit,
            pool=object(),
        )
        assert events == []

    async def test_creates_message_and_emits_user_start(
        self,
        pool,
        attempt_chat_factory,
    ):
        emit, events = recording_emit()
        graph = await attempt_chat_factory()
        await user_start_impl(
            {
                "sid": "s1",
                "chat_id": str(graph.attempt_chat.id),
                "run_id": str(graph.run.id),
                "session_id": str(graph.session.id),
            },
            emit=emit,
            pool=pool,
        )
        assert len(events) == 1
        assert events[0].event == "attempt_user_start"
        message_id = UUID(events[0].data["message_id"])
        async with pool.acquire() as conn:
            message = await get_message(conn, message_id)
            attempt_messages, total_count = await search_attempt_messages(
                conn,
                chat_ids=[graph.attempt_chat.id],
                bypass_mv=True,
                limit=100,
            )
        assert message is not None
        assert message.run_id == graph.run.id
        assert message.role == "user"
        assert total_count == 1
        assert len(attempt_messages) == 1
        assert attempt_messages[0].message_id == message_id
        assert attempt_messages[0].chat_id == graph.attempt_chat.id
        assert attempt_messages[0].completed is False


# ═══════════════════════════════════════════════════════════════════════════
# audio_stop_impl
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestAudioStopImpl:
    async def test_no_sid_emits_nothing(self):
        emit, events = recording_emit()
        await audio_stop_impl({"group_id": "g1"}, emit=emit)
        assert events == []

    async def test_no_session_emits_audio_ended(self):
        """Even without a session, emits audio_ended."""
        emit, events = recording_emit()
        await audio_stop_impl({"sid": "s1", "group_id": "g1"}, emit=emit)
        assert len(events) == 1
        assert events[0].event == "attempt_audio_ended"
        assert events[0].data["chat_id"] == "g1"

    async def test_with_session_cleans_up_and_emits(self, audio_session_factory):
        emit, events = recording_emit()
        await audio_session_factory()

        class FakeAudioAdapter:
            def __init__(self):
                self.stopped_sessions: list[str] = []

            async def stop_session(self, session) -> None:
                self.stopped_sessions.append(session.group_id)

        adapter = FakeAudioAdapter()

        await audio_stop_impl(
            {"sid": "s1", "group_id": "g1"},
            emit=emit,
            cleanup_audio_session_fn=lambda session: (
                audio_lifecycle.cleanup_audio_session(
                    session,
                    adapter=adapter,
                )
            ),
        )

        assert adapter.stopped_sessions == ["g1"]
        assert get_session_by_group_id("g1") is None
        assert events[0].data["chat_id"] == "c1"


# ═══════════════════════════════════════════════════════════════════════════
# audio_response_cancelled_impl
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestAudioResponseCancelledImpl:
    async def test_no_group_id_emits_nothing(self):
        emit, events = recording_emit()
        await audio_response_cancelled_impl({}, emit=emit)
        assert events == []

    async def test_no_session_emits_nothing(self):
        emit, events = recording_emit()
        await audio_response_cancelled_impl({"group_id": "g1"}, emit=emit)
        assert events == []

    async def test_emits_stopped_and_generate(self, audio_session_factory):
        emit, events = recording_emit()
        await audio_session_factory()
        await audio_response_cancelled_impl(
            {"group_id": "g1", "artifact_type": "agent"}, emit=emit
        )
        assert len(events) == 2
        assert events[0].event == "attempt_stopped"
        assert events[0].data["chat_id"] == "c1"
        assert events[1].event == "generate"
        assert events[1].data["group_id"] == "g1"


# ═══════════════════════════════════════════════════════════════════════════
# test_error_impl
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestTestErrorImpl:
    async def test_emits_test_error(self):
        emit, events = recording_emit()
        await _test_error_impl(
            {
                "sid": "s1",
                "invocation_id": "inv-1",
                "error_message": "bad input",
                "run_id": "r1",
                "error_type": "validation",
            },
            emit=emit,
        )
        assert len(events) == 1
        assert events[0].event == "test_error"
        assert events[0].data["message"] == "bad input"
        assert events[0].data["invocation_id"] == "inv-1"
        assert events[0].data["error_type"] == "validation"
        assert "test_inv-1" in events[0].data["rooms"]

    async def test_no_sid_still_emits(self):
        emit, events = recording_emit()
        await _test_error_impl({"invocation_id": "inv-1", "message": "oops"}, emit=emit)
        assert len(events) == 1
        assert events[0].data["rooms"] == []

    async def test_fallback_to_chat_id(self):
        emit, events = recording_emit()
        await _test_error_impl({"sid": "s1", "chat_id": "chat-1"}, emit=emit)
        assert events[0].data["invocation_id"] == "chat-1"

    async def test_default_message(self):
        emit, events = recording_emit()
        await _test_error_impl({"sid": "s1"}, emit=emit)
        assert events[0].data["message"] == "Test error"


# ═══════════════════════════════════════════════════════════════════════════
# test_progress_impl
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestProgressImpl:
    async def test_no_invocation_id_emits_nothing(self):
        emit, events = recording_emit()
        await _test_progress_impl({"sid": "s1"}, emit=emit)
        assert events == []

    async def test_emits_test_grade_start(self):
        emit, events = recording_emit()
        await _test_progress_impl(
            {
                "sid": "s1",
                "invocation_id": "inv-1",
                "run_id": "r1",
                "current_run": 2,
                "total_runs": 5,
                "message": "Grading...",
            },
            emit=emit,
        )
        assert len(events) == 1
        assert events[0].event == "test_grade_start"
        assert events[0].data["invocation_id"] == "inv-1"
        assert events[0].data["current_run"] == 2
        assert events[0].data["total_runs"] == 5
        assert events[0].data["message"] == "Grading..."
        assert events[0].data["rooms"] == ["s1", "test_inv-1"]

    async def test_fallback_to_chat_id(self):
        emit, events = recording_emit()
        await _test_progress_impl({"sid": "s1", "chat_id": "chat-1"}, emit=emit)
        assert events[0].data["invocation_id"] == "chat-1"

    async def test_no_sid_empty_rooms(self):
        emit, events = recording_emit()
        await _test_progress_impl({"invocation_id": "inv-1"}, emit=emit)
        assert events[0].data["rooms"] == []


# ═══════════════════════════════════════════════════════════════════════════
# test_run_done_impl
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestRunDoneImpl:
    async def test_no_invocation_id_emits_nothing(self):
        emit, events = recording_emit()
        await _test_run_done_impl({"sid": "s1"}, emit=emit)
        assert events == []

    async def test_emits_test_run_complete(self):
        emit, events = recording_emit()
        await _test_run_done_impl(
            {
                "sid": "s1",
                "invocation_id": "inv-1",
                "run_id": "r1",
                "original_run_resource_id": "orig-1",
                "tool_calls": [{"name": "tool1"}],
                "current_run": 2,
                "total_runs": 5,
            },
            emit=emit,
        )
        assert len(events) == 1
        assert events[0].event == "test_run_complete"
        assert events[0].data["invocation_id"] == "inv-1"
        assert events[0].data["run_id"] == "r1"
        assert events[0].data["original_run_resource_id"] == "orig-1"
        assert events[0].data["tool_calls"] == [{"name": "tool1"}]
        assert events[0].data["current_run"] == 2
        assert events[0].data["total_runs"] == 5
        assert events[0].data["remaining_runs"] == 3
        assert events[0].data["rooms"] == ["s1", "test_inv-1"]

    async def test_defaults_current_and_total(self):
        emit, events = recording_emit()
        await _test_run_done_impl({"sid": "s1", "invocation_id": "inv-1"}, emit=emit)
        assert events[0].data["current_run"] == 1
        assert events[0].data["total_runs"] == 1
        assert events[0].data["remaining_runs"] == 0

    async def test_no_run_id_is_none(self):
        emit, events = recording_emit()
        await _test_run_done_impl({"sid": "s1", "invocation_id": "inv-1"}, emit=emit)
        assert events[0].data["run_id"] is None
        assert events[0].data["original_run_resource_id"] is None


# ═══════════════════════════════════════════════════════════════════════════
# test_next_impl
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestNextImpl:
    async def _setup_test(self, conn, redis_client):
        profile = await create_profile(conn, redis_client, name="test-next-profile")
        session = await create_session(conn, profile_id=profile.id)
        group = await create_group(conn, session_id=session.id)
        run = await create_run(conn, group_id=group.id, session_id=session.id)
        test_call = await create_call(conn, run_id=run.id, session_id=session.id)
        test = await create_test(conn, call_id=test_call.id, profiles_id=profile.id)
        return test, run, session, group

    async def test_no_sid_emits_nothing(self):
        emit, events = recording_emit()
        await _test_next_impl({"test_id": "123"}, emit=emit, pool=object())
        assert events == []

    async def test_invalid_test_id_emits_error(self):
        emit, events = recording_emit()
        await _test_next_impl({"sid": "s1"}, emit=emit, pool=object())
        assert len(events) == 1
        assert events[0].bus == "client"
        assert events[0].event == "test_error"
        assert events[0].room == "s1"

    async def test_no_invocations_emits_all_complete(self, pool, redis_client):
        async with pool.acquire() as conn:
            test, _run, _session, _group = await self._setup_test(conn, redis_client)
            await refresh_test(conn)
            await refresh_test_invocation(conn)
        emit, events = recording_emit()
        await _test_next_impl(
            {"sid": "s1", "test_id": str(test.id)},
            emit=emit,
            pool=pool,
        )
        assert len(events) == 1
        assert events[0].bus == "client"
        assert events[0].event == "test_all_complete"
        assert events[0].data["success"] is True
        assert events[0].room == "s1"

    async def test_pending_invocation_emits_test_group(self, pool, redis_client):
        async with pool.acquire() as conn:
            test, run, session, group = await self._setup_test(conn, redis_client)
            invocation_call = await create_call(
                conn, run_id=run.id, session_id=session.id
            )
            invocation = await create_test_invocation(
                conn,
                test_id=test.id,
                call_id=invocation_call.id,
                group_id=group.id,
            )
            await refresh_test(conn)
            await refresh_test_invocation(conn)
        emit, events = recording_emit()
        await _test_next_impl(
            {"sid": "s1", "test_id": str(test.id)},
            emit=emit,
            pool=pool,
        )
        assert len(events) == 1
        assert events[0].bus == "internal"
        assert events[0].event == "test_group"
        assert events[0].data["sid"] == "s1"
        assert events[0].data["test_invocation_id"] == str(invocation.id)
        assert events[0].data["group_id"] == str(group.id)

    async def test_all_completed_emits_all_complete(self, pool, redis_client):
        async with pool.acquire() as conn:
            test, run, session, group = await self._setup_test(conn, redis_client)
            first_call = await create_call(conn, run_id=run.id, session_id=session.id)
            first_invocation = await create_test_invocation(
                conn,
                test_id=test.id,
                call_id=first_call.id,
                group_id=group.id,
            )
            second_call = await create_call(conn, run_id=run.id, session_id=session.id)
            second_invocation = await create_test_invocation(
                conn,
                test_id=test.id,
                call_id=second_call.id,
            )
            complete_first_call = await create_call(
                conn, run_id=run.id, session_id=session.id
            )
            await create_test_grade(
                conn,
                invocation_id=first_invocation.id,
                call_id=complete_first_call.id,
                run_id=run.id,
                time_taken=10,
                passed=True,
                score=90,
            )
            complete_second_call = await create_call(
                conn, run_id=run.id, session_id=session.id
            )
            await create_test_grade(
                conn,
                invocation_id=second_invocation.id,
                call_id=complete_second_call.id,
                run_id=run.id,
                time_taken=10,
                passed=True,
                score=85,
            )
            await refresh_test(conn)
            await refresh_test_invocation(conn)
        emit, events = recording_emit()
        await _test_next_impl(
            {"sid": "s1", "test_id": str(test.id)},
            emit=emit,
            pool=pool,
        )
        assert len(events) == 1
        assert events[0].bus == "client"
        assert events[0].event == "test_all_complete"
        assert events[0].data["invocation_id"] in {
            str(first_invocation.id),
            str(second_invocation.id),
        }
        assert events[0].data["total_runs"] == 2
        assert events[0].data["success"] is True


# ═══════════════════════════════════════════════════════════════════════════
# Grade extraction helpers
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractGradeHelpers:
    def test_extract_score(self):
        assert _extract_grade_score([{"result": {"score": 85}}]) == 85

    def test_extract_score_from_total(self):
        assert _extract_grade_score([{"result": {"total": 90}}]) == 90

    def test_extract_score_none(self):
        assert _extract_grade_score([{"result": {"other": 1}}]) is None

    def test_extract_score_empty(self):
        assert _extract_grade_score([]) is None

    def test_extract_passed(self):
        assert _extract_grade_passed([{"result": {"passed": True}}]) is True

    def test_extract_passed_false(self):
        assert _extract_grade_passed([{"result": {"passed": False}}]) is False

    def test_extract_passed_none(self):
        assert _extract_grade_passed([{"result": {}}]) is None

    def test_extract_feedback(self):
        assert _extract_grade_feedback([{"result": {"feedback": "good"}}]) == "good"

    def test_extract_feedback_empty_string(self):
        assert _extract_grade_feedback([{"result": {"feedback": ""}}]) is None

    def test_extract_feedback_none(self):
        assert _extract_grade_feedback([{"result": {}}]) is None


# ═══════════════════════════════════════════════════════════════════════════
# test_grade_complete_impl
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestGradeCompleteImpl:
    async def test_emits_test_grade_progress(self):
        emit, events = recording_emit()
        await _test_grade_complete_impl(
            {
                "sid": "s1",
                "grade_id": "g1",
                "invocation_id": "inv-1",
                "tool_results": [
                    {"result": {"score": 85, "passed": True, "feedback": "good"}}
                ],
            },
            emit=emit,
            pool=object(),
            profile_id="prof-1",
        )
        assert len(events) == 1
        assert events[0].event == "test_grade_progress"
        assert events[0].data["score"] == 85
        assert events[0].data["passed"] is True
        assert events[0].data["feedback"] == "good"
        assert events[0].data["grade_id"] == "g1"
        assert events[0].data["invocation_id"] == "inv-1"

    async def test_creates_token_when_run_and_session(self, pool, redis_client):
        async with pool.acquire() as conn:
            profile = await create_profile(conn, redis_client)
            session = await create_session(conn, profile_id=profile.id)
            group = await create_group(conn, session_id=session.id)
            run = await create_run(
                conn,
                group_id=group.id,
                session_id=session.id,
                profiles_id=profile.id,
            )

        emit, events = recording_emit()
        await _test_grade_complete_impl(
            {
                "sid": "s1",
                "grade_id": "g1",
                "invocation_id": "inv-1",
                "run_id": str(run.id),
                "session_id": str(session.id),
                "input_tokens": 100,
                "output_tokens": 50,
                "tool_results": [],
            },
            emit=emit,
            pool=pool,
            profile_id="prof-1",
        )

        async with pool.acquire() as conn:
            await refresh_tokens(conn)
            tokens = await search_tokens(conn, run_ids=[run.id], bypass_mv=True)

        assert len(events) == 1
        assert len(tokens) == 1
        assert tokens[0].run_id == run.id
        assert tokens[0].session_id == session.id
        assert tokens[0].input_tokens == 100
        assert tokens[0].output_tokens == 50

    async def test_skips_token_without_session(self):
        emit, events = recording_emit()
        await _test_grade_complete_impl(
            {
                "sid": "s1",
                "grade_id": "g1",
                "invocation_id": "inv-1",
                "run_id": "019b3be4-36f0-788c-9df2-481eb5917940",
                "tool_results": [],
            },
            emit=emit,
            pool=object(),
            profile_id="prof-1",
        )
        # Should still emit grade progress, just no token created
        assert len(events) == 1
        assert events[0].event == "test_grade_progress"

    async def test_rooms_include_test_prefix(self):
        emit, events = recording_emit()
        await _test_grade_complete_impl(
            {
                "sid": "s1",
                "invocation_id": "inv-1",
                "tool_results": [],
            },
            emit=emit,
            pool=object(),
            profile_id="prof-1",
        )
        assert "test_inv-1" in events[0].data["rooms"]
        assert "s1" in events[0].data["rooms"]


# ═══════════════════════════════════════════════════════════════════════════
# _find_next_run_id helper
# ═══════════════════════════════════════════════════════════════════════════


class TestFindNextRunId:
    def test_empty_runs(self):
        assert _find_next_run_id([], None) is None

    def test_first_run_no_prev(self):
        runs = [SimpleNamespace(run_id="r1"), SimpleNamespace(run_id="r2")]
        assert _find_next_run_id(runs, None) == "r1"

    def test_next_after_prev(self):
        runs = [
            SimpleNamespace(run_id="r1"),
            SimpleNamespace(run_id="r2"),
            SimpleNamespace(run_id="r3"),
        ]
        assert _find_next_run_id(runs, "r1") == "r2"
        assert _find_next_run_id(runs, "r2") == "r3"

    def test_last_run_returns_none(self):
        runs = [SimpleNamespace(run_id="r1"), SimpleNamespace(run_id="r2")]
        assert _find_next_run_id(runs, "r2") is None

    def test_unknown_prev_returns_none(self):
        runs = [SimpleNamespace(run_id="r1")]
        assert _find_next_run_id(runs, "unknown") is None


# ═══════════════════════════════════════════════════════════════════════════
# test_group_impl
# ═══════════════════════════════════════════════════════════════════════════

_RUNS_SEARCH = "app.tools.entries.runs.search"


@pytest.mark.asyncio
class TestGroupImpl:
    async def test_no_sid_emits_nothing(self):
        emit, events = recording_emit()
        await _test_group_impl({}, emit=emit, pool=object())
        assert events == []

    async def test_no_profile_emits_nothing(self):
        emit, events = recording_emit()
        await _test_group_impl({"sid": "s1"}, emit=emit, pool=object())
        assert events == []

    async def test_no_runs_emits_group_complete(self, pool):
        emit, events = recording_emit()
        await _test_group_impl(
            {
                "sid": "s1",
                "profile_id": "prof-1",
                "test_id": "019b3be4-36f0-788c-9df2-481eb5917940",
                "test_invocation_id": "019b3be4-36f0-788c-9df2-481eb5917941",
                "group_id": "019b3be4-36f0-788c-9df2-481eb5917942",
            },
            emit=emit,
            pool=pool,
        )
        assert len(events) == 1
        assert events[0].event == "test_group_complete"

    async def test_first_run_emits_test_run(self, pool, redis_client):
        async with pool.acquire() as conn:
            profile = await create_profile(conn, redis_client)
            session = await create_session(conn, profile_id=profile.id)
            group = await create_group(conn, session_id=session.id)
            first_run = await create_run(conn, group_id=group.id, session_id=session.id)
            await create_run(conn, group_id=group.id, session_id=session.id)

        emit, events = recording_emit()
        await _test_group_impl(
            {
                "sid": "s1",
                "profile_id": str(profile.id),
                "test_id": "019b3be4-36f0-788c-9df2-481eb5917940",
                "test_invocation_id": "019b3be4-36f0-788c-9df2-481eb5917941",
                "group_id": str(group.id),
            },
            emit=emit,
            pool=pool,
        )
        assert len(events) == 1
        assert events[0].event == "test_run"
        assert events[0].data["run_id"] == str(first_run.id)

    async def test_last_run_emits_group_complete(self, pool, redis_client):
        async with pool.acquire() as conn:
            profile = await create_profile(conn, redis_client)
            session = await create_session(conn, profile_id=profile.id)
            group = await create_group(conn, session_id=session.id)
            await create_run(conn, group_id=group.id, session_id=session.id)
            last_run = await create_run(conn, group_id=group.id, session_id=session.id)

        emit, events = recording_emit()
        await _test_group_impl(
            {
                "sid": "s1",
                "profile_id": str(profile.id),
                "test_id": "019b3be4-36f0-788c-9df2-481eb5917940",
                "test_invocation_id": "019b3be4-36f0-788c-9df2-481eb5917941",
                "group_id": str(group.id),
                "prev_run_id": str(last_run.id),
            },
            emit=emit,
            pool=pool,
        )
        assert len(events) == 1
        assert events[0].event == "test_group_complete"


# ═══════════════════════════════════════════════════════════════════════════
# test_start_impl
# ═══════════════════════════════════════════════════════════════════════════

_TEST_CREATE = "app.tools.entries.test.create"
_BENCHMARK_CREATE = "app.tools.entries.benchmark_test.create"
_REFRESH = "app.tools.entries.test_invocation.refresh"
_CACHE = "app.utils.cache.invalidate_tags"


@pytest.mark.asyncio
class TestStartImpl:
    async def test_no_sid_emits_nothing(self):
        emit, events = recording_emit()
        await _test_start_impl({}, emit=emit, pool=object())
        assert events == []

    async def test_no_profile_emits_nothing(self):
        emit, events = recording_emit()
        await _test_start_impl({"sid": "s1"}, emit=emit, pool=object())
        assert events == []

    async def test_invalid_profile_id_returns(self):
        emit, events = recording_emit()
        await _test_start_impl(
            {"sid": "s1", "profile_id": "not-a-uuid"},
            emit=emit,
            pool=object(),
        )
        assert events == []

    async def test_creates_test_and_emits_proceed(self, pool, redis_client):
        async with pool.acquire() as conn:
            profile = await create_profile(conn, redis_client)

        emit, events = recording_emit()
        await _test_start_impl(
            {
                "sid": "s1",
                "profile_id": str(profile.id),
                "profiles_id": str(profile.id),
            },
            emit=emit,
            pool=pool,
            redis=redis_client,
        )

        test_id = UUID(events[0].data["test_id"])
        async with pool.acquire() as conn:
            created_profiles_id = await conn.fetchval(
                "SELECT profiles_id FROM test_profiles_connection WHERE attempt_id = $1",
                test_id,
            )

        assert len(events) == 1
        assert events[0].event == "test_proceed"
        assert created_profiles_id == profile.id

    async def test_creates_benchmark_bridge_when_requested(self, pool, redis_client):
        async with pool.acquire() as conn:
            profile = await create_profile(conn, redis_client)
            session = await create_session(conn, profile_id=profile.id)
            benchmark = await create_benchmark(conn, session_id=session.id)

        emit, events = recording_emit()
        await _test_start_impl(
            {
                "sid": "s1",
                "profile_id": str(profile.id),
                "profiles_id": str(profile.id),
                "session_id": str(session.id),
                "benchmark_id": str(benchmark.id),
            },
            emit=emit,
            pool=pool,
            redis=redis_client,
        )

        test_id = UUID(events[0].data["test_id"])
        async with pool.acquire() as conn:
            bridge_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM benchmark_test_entry
                WHERE benchmark_id = $1 AND test_id = $2
                """,
                benchmark.id,
                test_id,
            )

        assert len(events) == 1
        assert events[0].event == "test_proceed"
        assert bridge_count == 1


# ═══════════════════════════════════════════════════════════════════════════
# test_proceed_impl
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestProceedImpl:
    async def _setup_test(self, conn, redis_client, *, is_dynamic=True):
        profile = await create_profile(conn, redis_client, name="test-proceed-profile")
        session = await create_session(conn, profile_id=profile.id)
        group = await create_group(conn, session_id=session.id)
        run = await create_run(conn, group_id=group.id, session_id=session.id)
        test_call = await create_call(conn, run_id=run.id, session_id=session.id)
        test = await create_test(
            conn,
            call_id=test_call.id,
            profiles_id=profile.id,
            is_dynamic=is_dynamic,
        )
        await refresh_test(conn)
        return SimpleNamespace(
            profile=profile,
            session=session,
            group=group,
            run=run,
            test=test,
        )

    async def _create_invocation(
        self,
        conn,
        graph,
        *,
        group_id=None,
        use_custom=False,
    ):
        invocation_call = await create_call(
            conn,
            run_id=graph.run.id,
            session_id=graph.session.id,
        )
        invocation = await create_test_invocation(
            conn,
            test_id=graph.test.id,
            call_id=invocation_call.id,
            group_id=group_id,
            use_custom=use_custom,
        )
        return invocation, invocation_call

    async def test_no_sid_emits_nothing(self):
        emit, events = recording_emit()
        await _test_proceed_impl({"sid": ""}, emit=emit, pool=object())
        assert events == []

    async def test_invalid_payload_emits_nothing(self):
        emit, events = recording_emit()
        await _test_proceed_impl(
            {"sid": "s1"},  # missing test_id
            emit=emit,
            pool=object(),
        )
        assert events == []

    async def test_complete_all_marks_all_and_emits_ended(self, pool, redis_client):
        async with pool.acquire() as conn:
            graph = await self._setup_test(conn, redis_client)
            invocation, _invocation_call = await self._create_invocation(conn, graph)
        emit, events = recording_emit()
        await _test_proceed_impl(
            {
                "sid": "s1",
                "test_id": str(graph.test.id),
                "complete_all": True,
            },
            emit=emit,
            pool=pool,
        )

        async with pool.acquire() as conn:
            completions = await search_test_invocation_completions(
                conn,
                invocation_ids=[invocation.id],
                bypass_mv=True,
            )

        assert len(completions) == 1
        assert len(events) == 1
        assert events[0].event == "test_ended"
        assert events[0].data["success"] is True

    async def test_all_completed_emits_ended(self, pool, redis_client):
        async with pool.acquire() as conn:
            graph = await self._setup_test(conn, redis_client)
            invocation, _invocation_call = await self._create_invocation(conn, graph)
            grade_call = await create_call(
                conn,
                run_id=graph.run.id,
                session_id=graph.session.id,
            )
            await create_test_grade(
                conn,
                invocation_id=invocation.id,
                call_id=grade_call.id,
                run_id=graph.run.id,
                time_taken=10,
                passed=True,
                score=90,
            )
            await refresh_test_invocation(conn)
        emit, events = recording_emit()
        await _test_proceed_impl(
            {
                "sid": "s1",
                "test_id": str(graph.test.id),
            },
            emit=emit,
            pool=pool,
        )

        assert len(events) == 1
        assert events[0].event == "test_ended"

    async def test_no_invocations_emits_error(self, pool, redis_client):
        async with pool.acquire() as conn:
            graph = await self._setup_test(conn, redis_client)
        emit, events = recording_emit()
        await _test_proceed_impl(
            {
                "sid": "s1",
                "test_id": str(graph.test.id),
            },
            emit=emit,
            pool=pool,
        )

        assert len(events) == 1
        assert events[0].event == "test_error"
        assert events[0].data["error_type"] == "proceed"

    async def test_use_custom_without_force_emits_started(self, pool, redis_client):
        async with pool.acquire() as conn:
            graph = await self._setup_test(conn, redis_client)
            invocation, _invocation_call = await self._create_invocation(
                conn,
                graph,
                use_custom=True,
            )
        emit, events = recording_emit()
        await _test_proceed_impl(
            {
                "sid": "s1",
                "test_id": str(graph.test.id),
            },
            emit=emit,
            pool=pool,
        )

        assert len(events) == 1
        assert events[0].event == "test_started"
        assert events[0].data["invocation_entry_id"] == str(invocation.id)

    async def test_next_invocation_creates_and_emits_started(
        self,
        pool,
        redis_client,
    ):
        async with pool.acquire() as conn:
            graph = await self._setup_test(conn, redis_client, is_dynamic=False)
            invocation, _invocation_call = await self._create_invocation(conn, graph)
        emit, events = recording_emit()
        await _test_proceed_impl(
            {
                "sid": "s1",
                "test_id": str(graph.test.id),
            },
            emit=emit,
            pool=pool,
        )

        new_invocation_id = UUID(events[0].data["test_invocation_id"])
        async with pool.acquire() as conn:
            started_invocations, _ = await search_test_invocation_entries_internal(
                conn,
                test_ids=[graph.test.id],
                bypass_mv=True,
                limit=100,
            )

        assert len(started_invocations) == 2
        assert len(events) == 1
        assert events[0].event == "test_invocation_started"
        assert events[0].data["is_dynamic"] is False
        assert str(new_invocation_id) == events[0].data["test_invocation_id"]

    async def test_completed_invocation_id_creates_completion_and_ends(
        self,
        pool,
        redis_client,
    ):
        async with pool.acquire() as conn:
            graph = await self._setup_test(conn, redis_client)
            invocation, _invocation_call = await self._create_invocation(conn, graph)
        emit, events = recording_emit()
        await _test_proceed_impl(
            {
                "sid": "s1",
                "test_id": str(graph.test.id),
                "completed_invocation_id": str(invocation.id),
            },
            emit=emit,
            pool=pool,
        )

        async with pool.acquire() as conn:
            completions = await search_test_invocation_completions(
                conn,
                invocation_ids=[invocation.id],
                bypass_mv=True,
            )

        assert len(completions) == 1
        assert len(events) == 1
        assert events[0].event == "test_ended"


# ═══════════════════════════════════════════════════════════════════════════
# test_run_impl
# ═══════════════════════════════════════════════════════════════════════════

_RUN_CREATE = "app.tools.entries.runs.create"


@pytest.mark.asyncio
class TestRunImpl:
    async def _setup_graph(self, conn, redis_client):
        profile = await create_profile(conn, redis_client, name="test-run-profile")
        session = await create_session(conn, profile_id=profile.id)
        group = await create_group(conn, session_id=session.id)
        run = await create_run(
            conn,
            group_id=group.id,
            session_id=session.id,
            profiles_id=profile.id,
        )
        test_call = await create_call(conn, run_id=run.id, session_id=session.id)
        test = await create_test(conn, call_id=test_call.id, profiles_id=profile.id)
        return SimpleNamespace(
            profile=profile,
            session=session,
            group=group,
            run=run,
            test=test,
        )

    async def test_no_sid_emits_nothing(self):
        emit, events = recording_emit()
        await _test_run_impl({"sid": ""}, emit=emit, pool=object())
        assert events == []

    async def test_no_profile_id_emits_nothing(self):
        emit, events = recording_emit()
        await _test_run_impl(
            {"sid": "s1", "profile_id": ""},
            emit=emit,
            pool=object(),
        )
        assert events == []

    async def test_invalid_payload_emits_nothing(self):
        emit, events = recording_emit()
        await _test_run_impl(
            {"sid": "s1", "profile_id": "p1"},  # missing test_id etc
            emit=emit,
            pool=object(),
        )
        assert events == []

    async def test_no_invocation_emits_error(self, pool):
        emit, events = recording_emit()
        await _test_run_impl(
            {
                "sid": "s1",
                "profile_id": "019b3be4-36f0-788c-9df2-481eb5917941",
                "test_id": "019b3be4-36f0-788c-9df2-481eb5917940",
                "test_invocation_id": "019b3be4-36f0-788c-9df2-481eb5917942",
                "run_id": "019b3be4-36f0-788c-9df2-481eb5917943",
            },
            emit=emit,
            pool=pool,
        )

        assert len(events) == 1
        assert events[0].event == "test_error"
        assert events[0].data["error_type"] == "run"

    async def test_no_messages_emits_error(self, pool, redis_client):
        async with pool.acquire() as conn:
            graph = await self._setup_graph(conn, redis_client)
            invocation_call = await create_call(
                conn,
                run_id=graph.run.id,
                session_id=graph.session.id,
            )
            invocation = await create_test_invocation(
                conn,
                test_id=graph.test.id,
                call_id=invocation_call.id,
                group_id=graph.group.id,
            )
        emit, events = recording_emit()
        await _test_run_impl(
            {
                "sid": "s1",
                "profile_id": str(graph.profile.id),
                "profiles_id": str(graph.profile.id),
                "session_id": str(graph.session.id),
                "test_id": str(graph.test.id),
                "test_invocation_id": str(invocation.id),
                "run_id": str(graph.run.id),
            },
            emit=emit,
            pool=pool,
        )

        assert len(events) == 1
        assert events[0].event == "test_error"
        assert "No messages" in events[0].data["message"]

    async def test_happy_path_emits_run_started_and_generate(
        self,
        pool,
        redis_client,
    ):
        async with pool.acquire() as conn:
            graph = await self._setup_graph(conn, redis_client)
            await create_message(conn, run_id=graph.run.id, role="user")
            await create_message(conn, run_id=graph.run.id, role="assistant")
            invocation_call = await create_call(
                conn,
                run_id=graph.run.id,
                session_id=graph.session.id,
            )
            invocation = await create_test_invocation(
                conn,
                test_id=graph.test.id,
                call_id=invocation_call.id,
                group_id=graph.group.id,
            )
        emit, events = recording_emit()
        await _test_run_impl(
            {
                "sid": "s1",
                "profile_id": str(graph.profile.id),
                "profiles_id": str(graph.profile.id),
                "session_id": str(graph.session.id),
                "test_id": str(graph.test.id),
                "test_invocation_id": str(invocation.id),
                "run_id": str(graph.run.id),
            },
            emit=emit,
            pool=pool,
        )

        new_run_id = UUID(events[0].data["run_id"])
        assistant_message_id = UUID(events[0].data["message_id"])
        async with pool.acquire() as conn:
            copied_messages, _ = await search_messages(
                conn,
                run_ids=[new_run_id],
                sort_order="asc",
                bypass_mv=True,
                limit=100,
            )

        roles = [message.role for message in copied_messages]
        ids = [message.message_id for message in copied_messages]
        assert len(events) == 2
        assert events[0].event == "test_run_started"
        assert roles == ["user", "assistant"]
        assert assistant_message_id in ids
        assert events[1].event == "generate_artifact"
        assert events[1].data["artifact_type"] == "test"


# ═══════════════════════════════════════════════════════════════════════════
# user_complete_impl
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestUserCompleteImpl:
    async def test_no_sid_emits_nothing(self):
        emit, events = recording_emit()
        await _user_complete_impl(
            {"sid": "", "chat_id": "c1", "run_id": "r1", "content": "hi"},
            emit=emit,
            pool=object(),
        )
        assert events == []

    async def test_no_content_emits_nothing(self):
        emit, events = recording_emit()
        await _user_complete_impl(
            {"sid": "s1", "chat_id": "c1", "run_id": "r1", "content": ""},
            emit=emit,
            pool=object(),
        )
        assert events == []

    async def test_no_open_message_emits_nothing(self, pool, attempt_chat_factory):
        graph = await attempt_chat_factory()
        emit, events = recording_emit()
        await _user_complete_impl(
            {
                "sid": "s1",
                "chat_id": str(graph.attempt_chat.id),
                "run_id": str(graph.run.id),
                "content": "hello",
                "session_id": str(graph.session.id),
            },
            emit=emit,
            pool=pool,
        )
        assert events == []

    async def test_happy_path_emits_user_complete(self, pool, attempt_chat_factory):
        graph = await attempt_chat_factory()
        async with pool.acquire() as conn:
            open_message = await create_message(conn, run_id=graph.run.id, role="user")
            open_call = await create_call(
                conn,
                run_id=graph.run.id,
                session_id=graph.session.id,
            )
            await create_attempt_message(
                conn,
                chat_id=graph.attempt_chat.id,
                message_id=open_message.id,
                call_id=open_call.id,
            )
        emit, events = recording_emit()
        await _user_complete_impl(
            {
                "sid": "s1",
                "chat_id": str(graph.attempt_chat.id),
                "run_id": str(graph.run.id),
                "content": "hello world",
                "session_id": str(graph.session.id),
            },
            emit=emit,
            pool=pool,
        )

        assert len(events) == 1
        assert events[0].event == "attempt_user_complete"
        assert events[0].data["message_id"] == str(open_message.id)
        assert events[0].data["content"] == "hello world"
        async with pool.acquire() as conn:
            contents = await search_attempt_contents(
                conn,
                message_ids=[open_message.id],
                bypass_mv=True,
                limit=100,
            )
            completions = await search_attempt_message_completions(
                conn,
                attempt_message_ids=[open_message.id],
                bypass_mv=True,
                limit=100,
            )
            attempt_messages, _ = await search_attempt_messages(
                conn,
                chat_ids=[graph.attempt_chat.id],
                bypass_mv=True,
                limit=100,
            )
        assert len(contents) == 1
        assert contents[0].message_id == open_message.id
        assert contents[0].content == "hello world"
        assert len(completions) == 1
        assert completions[0].attempt_message_id == open_message.id
        matching_message = next(
            item for item in attempt_messages if item.message_id == open_message.id
        )
        assert matching_message.completed is True

    async def test_filters_completed_messages(self, pool, attempt_chat_factory):
        graph = await attempt_chat_factory()
        async with pool.acquire() as conn:
            completed_message = await create_message(
                conn,
                run_id=graph.run.id,
                role="user",
            )
            completed_call = await create_call(
                conn,
                run_id=graph.run.id,
                session_id=graph.session.id,
            )
            await create_attempt_message(
                conn,
                chat_id=graph.attempt_chat.id,
                message_id=completed_message.id,
                call_id=completed_call.id,
            )
            completion_call = await create_call(
                conn,
                run_id=graph.run.id,
                session_id=graph.session.id,
            )
            await create_attempt_message_completion(
                conn,
                attempt_message_id=completed_message.id,
                call_id=completion_call.id,
            )
            assistant_message = await create_message(
                conn,
                run_id=graph.run.id,
                role="assistant",
            )
            assistant_call = await create_call(
                conn,
                run_id=graph.run.id,
                session_id=graph.session.id,
            )
            await create_attempt_message(
                conn,
                chat_id=graph.attempt_chat.id,
                message_id=assistant_message.id,
                call_id=assistant_call.id,
            )
        emit, events = recording_emit()
        await _user_complete_impl(
            {
                "sid": "s1",
                "chat_id": str(graph.attempt_chat.id),
                "run_id": str(graph.run.id),
                "content": "hello",
                "session_id": str(graph.session.id),
            },
            emit=emit,
            pool=pool,
        )
        assert events == []


# ═══════════════════════════════════════════════════════════════════════════
# speech_complete_impl
# ═══════════════════════════════════════════════════════════════════════════

_UPLOAD_CREATE = "app.tools.entries.uploads.create"


@pytest.mark.asyncio
class TestSpeechCompleteImpl:
    async def test_no_group_id_emits_nothing(self):
        emit, events = recording_emit()
        await _speech_complete_impl({"group_id": ""}, emit=emit, pool=object())
        assert events == []

    async def test_no_session_emits_nothing(self, pool):
        emit, events = recording_emit()
        await _speech_complete_impl({"group_id": "g1"}, emit=emit, pool=pool)
        assert events == []

    async def test_empty_transcript_emits_nothing(self, pool, audio_session_factory):
        await audio_session_factory()
        emit, events = recording_emit()
        await _speech_complete_impl(
            {"group_id": "g1", "transcript": ""},
            emit=emit,
            pool=pool,
        )
        assert events == []

    async def test_transcript_only_emits_received_complete(
        self,
        pool,
        audio_session_factory,
    ):
        await audio_session_factory()
        emit, events = recording_emit()
        await _speech_complete_impl(
            {"group_id": "g1", "transcript": "hello world"},
            emit=emit,
            pool=pool,
        )

        assert len(events) == 1
        assert events[0].event == "attempt_user_received_complete"
        assert events[0].data["content"] == "hello world"
        assert events[0].data["audio_upload_id"] is None

    async def test_with_audio_creates_upload(
        self,
        pool,
        audio_session_factory,
        tmp_path,
    ):
        test_session_id = "00000000-0000-0000-0000-0000000000aa"
        await audio_session_factory(session_id=test_session_id)
        emit, events = recording_emit()
        await _speech_complete_impl(
            {
                "group_id": "g1",
                "transcript": "hello",
                "audio": b"fake-audio-bytes",
            },
            emit=emit,
            pool=pool,
            session_id=UUID(test_session_id),
            audio_folder=str(tmp_path),
        )

        assert len(events) == 1
        upload_id = UUID(events[0].data["audio_upload_id"])
        async with pool.acquire() as conn:
            upload = await get_upload(conn, upload_id)
        assert upload is not None
        assert upload.session_id == UUID(test_session_id)
        assert upload.mime_type == "audio/pcm16"
        assert upload.size == len(b"fake-audio-bytes")
        assert upload.file_path.endswith(".pcm16")
        assert (tmp_path / upload.file_path.removeprefix("audio/")).exists()


# ═══════════════════════════════════════════════════════════════════════════
# attempt_start_impl
# ═══════════════════════════════════════════════════════════════════════════

_PROFILE_CTX = "app.infra.profile_identity_context"
_ATTEMPT_CREATE = "app.tools.entries.attempt.create"
_ATTEMPT_REFRESH = "app.tools.entries.attempt.refresh"
_ATTEMPT_CHAT_REFRESH = "app.tools.entries.attempt_chat.refresh"
_ATTEMPT_PRACTICE = "app.tools.entries.attempt_practice.create"
_ATTEMPT_HOME = "app.tools.entries.attempt_home.create"
_CALLS_CREATE = "app.tools.entries.calls.create"
_PERSONA_CREATE = "app.tools.entries.persona.create"
_PRACTICE_GET = "app.tools.entries.practice.get"
_PRACTICE_CHAT_SEARCH = "app.tools.entries.practice_chat.search"
_PROFILE_PERSONAS_GET = "app.tools.resources.profile_personas.get"
_SIMULATIONS_GET = "app.tools.resources.simulations.get"


@pytest.mark.asyncio
class TestAttemptStartImpl:
    async def test_no_sid_emits_nothing(self):
        emit, events = recording_emit()
        await _attempt_start_impl(
            {"sid": ""},
            emit=emit,
            pool=object(),
            profile_id="p1",
            session_id="s1",
        )
        assert events == []

    async def test_invalid_payload_emits_nothing(self):
        emit, events = recording_emit()
        await _attempt_start_impl(
            {"sid": "s1"},  # missing practice_id/home_id
            emit=emit,
            pool=object(),
            profile_id="019b3be4-36f0-788c-9df2-481eb5917941",
            session_id="019b3be4-36f0-788c-9df2-481eb5917942",
        )
        assert events == []

    async def test_no_profile_resource_emits_error(self, pool):
        emit, events = recording_emit()
        await _attempt_start_impl(
            {
                "sid": "s1",
                "practice_id": "019b3be4-36f0-788c-9df2-481eb5917950",
                "group_id": "019b3be4-36f0-788c-9df2-481eb5917951",
            },
            emit=emit,
            pool=pool,
            profile_id="019b3be4-36f0-788c-9df2-481eb5917941",
            session_id="019b3be4-36f0-788c-9df2-481eb5917942",
        )

        assert len(events) == 1
        assert events[0].event == "attempt_error"
        assert events[0].data["error_type"] == "start"

    async def test_happy_path_practice_emits_proceed(
        self,
        pool,
        redis_client,
        profile_identity_factory,
    ):
        fixture = await profile_identity_factory()

        async with pool.acquire() as conn:
            session = await create_session(conn, profile_id=fixture.profile_resource_id)
            group = await create_group(conn, session_id=session.id)
            persona_resource = await create_persona_resource(
                conn,
                redis_client,
                name="attempt-start-persona",
            )
            profile_persona = await create_profile_persona(
                conn,
                profile_id=fixture.profile_resource_id,
                persona_id=persona_resource.id,
                redis=redis_client,
            )
            simulation = await create_simulation(
                conn,
                redis_client,
                name="Attempt Start Sim",
                description="Attempt Start Description",
            )
            practice = await create_practice(
                conn,
                session_id=session.id,
                cohorts_ids=[],
                departments_ids=[],
                simulations_ids=[simulation.id],
                profiles_ids=[fixture.profile_resource_id],
                profile_personas_ids=[profile_persona.id],
                simulation_availability_ids=[],
                simulation_positions_ids=[],
            )
            chat_one = await create_chat(conn, session_id=session.id)
            chat_two = await create_chat(conn, session_id=session.id)
            await create_practice_chat(
                conn,
                practice_id=practice.id,
                chat_id=chat_one.id,
                session_id=session.id,
            )
            await create_practice_chat(
                conn,
                practice_id=practice.id,
                chat_id=chat_two.id,
                session_id=session.id,
            )
            await refresh_practice(conn)
            await refresh_practice_chat(conn)

        emit, events = recording_emit()
        await _attempt_start_impl(
            {
                "sid": "s1",
                "practice_id": str(practice.id),
                "group_id": str(group.id),
            },
            emit=emit,
            pool=pool,
            redis=redis_client,
            profile_id=str(fixture.artifact_id),
            session_id=str(session.id),
        )

        assert len(events) == 1
        assert events[0].event == "attempt_proceed"
        attempt_id = UUID(events[0].data["attempt_id"])

        async with pool.acquire() as conn:
            attempts = await get_attempts(conn, [attempt_id])

        assert len(attempts) == 1
        assert attempts[0].profile_id == fixture.profile_resource_id
        assert attempts[0].practice is True
        assert attempts[0].num_chats == 2

    async def test_error_emits_attempt_error(
        self, pool, redis_client, profile_identity_factory
    ):
        fixture = await profile_identity_factory()
        async with pool.acquire() as conn:
            session = await create_session(conn, profile_id=fixture.profile_resource_id)
            group = await create_group(conn, session_id=session.id)

        emit, events = recording_emit()
        await _attempt_start_impl(
            {
                "sid": "s1",
                "practice_id": str(nonexistent_id()),
                "group_id": str(group.id),
            },
            emit=emit,
            pool=pool,
            redis=redis_client,
            profile_id=str(fixture.artifact_id),
            session_id=str(session.id),
        )

        assert len(events) == 1
        assert events[0].event == "attempt_error"
        assert events[0].data["error_type"] == "start"


# ═══════════════════════════════════════════════════════════════════════════
# emit_chat_generate_impl
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestEmitChatGenerateImpl:
    async def test_emits_generate_event(self, pool, redis_client):
        async with pool.acquire() as conn:
            profile = await create_profile(conn, redis_client)
            session = await create_session(conn, profile_id=profile.id)
            source_group = await create_group(conn, session_id=session.id)
            source_run = await create_run(
                conn,
                group_id=source_group.id,
                session_id=session.id,
                profiles_id=profile.id,
            )
            chat_entry = await create_chat(conn, session_id=session.id)

        emit, events = recording_emit()
        await _emit_chat_generate_impl(
            emit=emit,
            pool=pool,
            sid="s1",
            profile_id=profile.id,
            profiles_id=profile.id,
            session_id=session.id,
            attempt_id=source_run.id,
            chat_entry_id=chat_entry.id,
            department_id=profile.id,
            attempt_chat_id=source_group.id,
        )

        generated_group_id = UUID(events[0].data["group_id"])
        generated_run_id = UUID(events[0].data["run_id"])
        async with pool.acquire() as conn:
            groups = await get_groups(conn, [generated_group_id], bypass_mv=True)
            run = await get_run(conn, generated_run_id)

        assert len(events) == 1
        assert events[0].event == "generate"
        assert events[0].data["profile_id"] == str(profile.id)
        assert events[0].data["artifact_id"] == str(chat_entry.id)
        assert events[0].data["metadata"]["attempt_id"] == str(source_run.id)
        assert groups[0].session_id == session.id
        assert run is not None
        assert run.group_id == generated_group_id
        assert run.session_id == session.id

    async def test_uses_default_resource_types(self, pool, redis_client):
        async with pool.acquire() as conn:
            profile = await create_profile(conn, redis_client)
            session = await create_session(conn, profile_id=profile.id)
            chat_entry = await create_chat(conn, session_id=session.id)

        emit, events = recording_emit()
        await _emit_chat_generate_impl(
            emit=emit,
            pool=pool,
            sid="s1",
            profile_id=profile.id,
            profiles_id=profile.id,
            session_id=session.id,
            attempt_id=profile.id,
            chat_entry_id=chat_entry.id,
            department_id=profile.id,
            attempt_chat_id=None,
        )

        assert events[0].data["resource_types"] == [
            "personas",
            "scenarios",
            "parameters",
            "fields",
        ]
        assert events[0].data["metadata"]["attempt_chat_id"] is None

    async def test_passes_custom_resource_types_and_draft_id(
        self,
        pool,
        redis_client,
    ):
        async with pool.acquire() as conn:
            profile = await create_profile(conn, redis_client)
            session = await create_session(conn, profile_id=profile.id)
            chat_entry = await create_chat(conn, session_id=session.id)

        draft = UUID(int=99)
        emit, events = recording_emit()
        await _emit_chat_generate_impl(
            emit=emit,
            pool=pool,
            sid="s1",
            profile_id=profile.id,
            profiles_id=profile.id,
            session_id=session.id,
            attempt_id=profile.id,
            chat_entry_id=chat_entry.id,
            department_id=profile.id,
            attempt_chat_id=profile.id,
            resource_types=["personas", "documents"],
            draft_id=draft,
        )

        assert events[0].data["resource_types"] == ["personas", "documents"]
        assert events[0].data["draft_id"] == str(draft)


# ═══════════════════════════════════════════════════════════════════════════
# attempt_proceed_impl
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestAttemptProceedImpl:
    _RUNS = "app.tools.entries.runs.create.create_run"
    _GET_ATTEMPTS = "app.tools.entries.attempt.get.get_attempts"
    _BRIDGES = "app.tools.entries.attempt_chat_bridge.search.search_attempt_chat_bridges"
    _SEARCH_CHATS = (
        "app.tools.entries.attempt_chat.search.search_attempt_chats"
    )
    _PRACTICE_ENTRIES = "app.tools.entries.attempt_practice.search.search_attempt_practice_entries"
    _HOME_ENTRIES = (
        "app.tools.entries.attempt_home.search.search_attempt_homes"
    )
    _PRACTICE_CHATS = (
        "app.tools.entries.practice_chat.search.search_practice_chats"
    )
    _HOME_CHATS = "app.tools.entries.home_chat.search.search_home_chats"
    _CHAT_ENTRIES = "app.tools.entries.chat.get.get_chat_entries_internal"
    _CREATE_CALL = "app.tools.entries.calls.create.create_call"
    _CREATE_CHAT = "app.tools.entries.attempt_chat.create.create_attempt_chat"
    _CREATE_BRIDGE = "app.tools.entries.attempt_chat_bridge.create.create_attempt_chat_bridge"
    _REFRESH_ATTEMPT = "app.tools.entries.attempt.refresh.refresh_attempt"
    _REFRESH_CHAT = (
        "app.tools.entries.attempt_chat.refresh.refresh_attempt_chat"
    )
    _CHAT_COMPLETION = "app.tools.entries.attempt_chat_completion.create.create_attempt_chat_completion"
    _EMIT_GENERATE = f"{_P}.emit_chat_generate_impl"

    async def test_no_sid_returns_early(self):
        emit, events = recording_emit()
        await _attempt_proceed_impl(
            {"sid": ""},
            emit=emit,
            pool=object(),
            profile_id="019b3be4-36f0-788c-9df2-481eb5917941",
            session_id="019b3be4-36f0-788c-9df2-481eb5917942",
        )
        assert len(events) == 0

    async def test_invalid_payload_returns_early(self):
        emit, events = recording_emit()
        await _attempt_proceed_impl(
            {"sid": "s1"},  # missing attempt_id, group_id
            emit=emit,
            pool=object(),
            profile_id="019b3be4-36f0-788c-9df2-481eb5917941",
            session_id="019b3be4-36f0-788c-9df2-481eb5917942",
        )
        assert len(events) == 0

    async def test_complete_all_emits_ended(self, pool, attempt_chat_factory):
        graph = await attempt_chat_factory()
        emit, events = recording_emit()
        await _attempt_proceed_impl(
            {
                "sid": "s1",
                "attempt_id": str(graph.attempt.id),
                "group_id": str(graph.group.id),
                "complete_all": True,
            },
            emit=emit,
            pool=pool,
            profile_id=str(graph.profile.id),
            session_id=str(graph.session.id),
            profiles_id=graph.profile.id,
        )

        async with pool.acquire() as conn:
            completions = await search_attempt_chat_completions(
                conn,
                chat_ids=[graph.attempt_chat.id],
                bypass_mv=True,
            )

        assert len(events) == 1
        assert events[0].event == "attempt_ended"
        assert events[0].data["all_scenarios_complete"] is True
        assert len(completions) == 1

    async def test_all_done_emits_ended(self, pool, redis_client):
        async with pool.acquire() as conn:
            profile = await create_profile(conn, redis_client)
            session = await create_session(conn, profile_id=profile.id)
            group = await create_group(conn, session_id=session.id)
            run = await create_run(
                conn,
                group_id=group.id,
                session_id=session.id,
                profiles_id=profile.id,
            )
            attempt_call = await create_call(
                conn,
                run_id=run.id,
                session_id=session.id,
            )
            persona = await create_persona(conn, session_id=session.id)
            attempt = await create_attempt(
                conn,
                call_id=attempt_call.id,
                user_persona_id=persona.id,
                profiles_id=profile.id,
                practice=True,
                num_chats=1,
            )
            practice = await create_practice(
                conn,
                session_id=session.id,
                cohorts_ids=[],
                departments_ids=[],
                simulations_ids=[],
                profiles_ids=[profile.id],
                profile_personas_ids=[],
                simulation_availability_ids=[],
                simulation_positions_ids=[],
            )
            chat = await create_chat(conn, session_id=session.id)
            await create_practice_chat(
                conn,
                practice_id=practice.id,
                chat_id=chat.id,
                session_id=session.id,
            )
            attempt_chat_call = await create_call(
                conn,
                run_id=run.id,
                session_id=session.id,
            )
            attempt_chat = await create_attempt_chat(
                conn,
                call_id=attempt_chat_call.id,
                group_id=group.id,
                chat_id=chat.id,
            )
            await create_attempt_chat_bridge(
                conn,
                attempt_id=attempt.id,
                attempt_chat_id=attempt_chat.id,
                session_id=session.id,
            )
            await create_attempt_practice(
                conn,
                attempt_id=attempt.id,
                practice_id=practice.id,
                session_id=session.id,
            )
            await refresh_attempt(conn)
        async with pool.acquire() as conn:
            await refresh_attempt(conn)
        emit, events = recording_emit()
        await _attempt_proceed_impl(
            {
                "sid": "s1",
                "attempt_id": str(attempt.id),
                "group_id": str(group.id),
            },
            emit=emit,
            pool=pool,
            profile_id=str(profile.id),
            session_id=str(session.id),
            profiles_id=profile.id,
        )

        assert len(events) == 1
        assert events[0].event == "attempt_ended"
        assert events[0].data["all_scenarios_complete"] is True

    async def _setup_practice_attempt(
        self,
        conn,
        redis_client,
        *,
        parent_chat_overrides: dict | None = None,
    ):
        profile = await create_profile(conn, redis_client)
        session = await create_session(conn, profile_id=profile.id)
        group = await create_group(conn, session_id=session.id)
        run = await create_run(
            conn,
            group_id=group.id,
            session_id=session.id,
            profiles_id=profile.id,
        )
        attempt_call = await create_call(conn, run_id=run.id, session_id=session.id)
        persona = await create_persona(conn, session_id=session.id)
        attempt = await create_attempt(
            conn,
            call_id=attempt_call.id,
            user_persona_id=persona.id,
            profiles_id=profile.id,
            practice=True,
            num_chats=2,
        )
        practice = await create_practice(
            conn,
            session_id=session.id,
            cohorts_ids=[],
            departments_ids=[],
            simulations_ids=[],
            profiles_ids=[profile.id],
            profile_personas_ids=[],
            simulation_availability_ids=[],
            simulation_positions_ids=[],
        )
        department = await create_department(conn, redis=redis_client)
        parent_chat = await create_chat(
            conn,
            session_id=session.id,
            department_ids=[department.id],
            **(parent_chat_overrides or {}),
        )
        await create_practice_chat(
            conn,
            practice_id=practice.id,
            chat_id=parent_chat.id,
            session_id=session.id,
        )
        await create_attempt_practice(
            conn,
            attempt_id=attempt.id,
            practice_id=practice.id,
            session_id=session.id,
        )
        await refresh_chat(conn)
        await refresh_attempt(conn)
        return SimpleNamespace(
            profile=profile,
            session=session,
            group=group,
            run=run,
            attempt=attempt,
            parent_chat=parent_chat,
            department=department,
        )

    async def test_no_generation_emits_chat_started(self, pool, redis_client):
        async with pool.acquire() as conn:
            graph = await self._setup_practice_attempt(conn, redis_client)

        emit, events = recording_emit()
        await _attempt_proceed_impl(
            {
                "sid": "s1",
                "attempt_id": str(graph.attempt.id),
                "group_id": str(graph.group.id),
            },
            emit=emit,
            pool=pool,
            profile_id=str(graph.profile.id),
            session_id=str(graph.session.id),
            profiles_id=graph.profile.id,
        )

        attempt_chat_id = UUID(events[0].data["chat_id"])
        async with pool.acquire() as conn:
            attempt_chats, _ = await search_attempt_chats(
                conn,
                attempt_chat_ids=[attempt_chat_id],
                bypass_mv=True,
                limit=10,
            )
            bridges = await search_attempt_chat_bridges(
                conn,
                attempt_ids=[graph.attempt.id],
                bypass_mv=True,
                limit=10,
            )

        assert len(events) == 1
        assert events[0].event == "attempt_chat_started"
        assert events[0].data["attempt_id"] == str(graph.attempt.id)
        assert len(attempt_chats) == 1
        assert attempt_chats[0].chat_entry_id == graph.parent_chat.id
        assert len(bridges) == 1
        assert bridges[0].attempt_chat_id == attempt_chat_id

    async def test_with_generation_calls_emit_chat_generate(
        self,
        pool,
        redis_client,
    ):
        async with pool.acquire() as conn:
            graph = await self._setup_practice_attempt(
                conn,
                redis_client,
                parent_chat_overrides={"generate_personas": True},
            )

        emit, events = recording_emit()
        await _attempt_proceed_impl(
            {
                "sid": "s1",
                "attempt_id": str(graph.attempt.id),
                "group_id": str(graph.group.id),
            },
            emit=emit,
            pool=pool,
            profile_id=str(graph.profile.id),
            session_id=str(graph.session.id),
            profiles_id=graph.profile.id,
        )

        assert len(events) == 1
        assert events[0].event == "generate"
        assert events[0].data["resource_types"] == ["personas"]
        generated_attempt_chat_id = UUID(events[0].data["metadata"]["attempt_chat_id"])
        async with pool.acquire() as conn:
            bridges = await search_attempt_chat_bridges(
                conn,
                attempt_ids=[graph.attempt.id],
                bypass_mv=True,
                limit=10,
            )
        assert len(bridges) == 1
        assert bridges[0].attempt_chat_id == generated_attempt_chat_id

    async def test_user_choice_emits_started(self, pool, redis_client):
        async with pool.acquire() as conn:
            graph = await self._setup_practice_attempt(
                conn,
                redis_client,
                parent_chat_overrides={"use_custom": True},
            )

        emit, events = recording_emit()
        await _attempt_proceed_impl(
            {
                "sid": "s1",
                "attempt_id": str(graph.attempt.id),
                "group_id": str(graph.group.id),
            },
            emit=emit,
            pool=pool,
            profile_id=str(graph.profile.id),
            session_id=str(graph.session.id),
            profiles_id=graph.profile.id,
        )

        assert len(events) == 1
        assert events[0].event == "attempt_started"
        assert events[0].data["chat_entry_id"] == str(graph.parent_chat.id)

    async def test_error_emits_attempt_error(self, pool, redis_client):
        async with pool.acquire() as conn:
            profile = await create_profile(conn, redis_client)
            session = await create_session(conn, profile_id=profile.id)
            group = await create_group(conn, session_id=session.id)

        emit, events = recording_emit()
        await _attempt_proceed_impl(
            {
                "sid": "s1",
                "attempt_id": str(nonexistent_id()),
                "group_id": str(group.id),
            },
            emit=emit,
            pool=pool,
            redis=redis_client,
            profile_id=str(profile.id),
            session_id=str(session.id),
            profiles_id=profile.id,
        )

        assert len(events) == 1
        assert events[0].event == "attempt_error"
        assert events[0].data["error_type"] == "proceed"
