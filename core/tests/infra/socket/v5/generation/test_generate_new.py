"""Tests for generate_new_impl using real runs context and audio session state."""

from __future__ import annotations

import pytest

from app.infra.websocket.generate_new_impl import generate_new_impl
from app.infra.websocket.session_store import (
    _session_store,
    get_session_by_group_id,
    get_session_by_run_id,
)
from app.infra.websocket.session_store import (
    create_session as create_audio_session,
)
from app.infra.websocket.socket_event import recording_emit
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.resources.profiles.create import create_profile

pytestmark = pytest.mark.asyncio


def _base_data(**overrides: object) -> dict:
    d: dict = {
        "sid": "s1",
        "profile_id": "00000000-0000-0000-0000-000000000001",
        "session_id": "sess-1",
        "artifact_types": [{"name": "agent", "operation": "get"}],
        "resource_types": [],
    }
    d.update(overrides)
    return d


@pytest.fixture(autouse=True)
def cleanup_audio_store():
    _session_store.clear()
    yield
    _session_store.clear()


class TestGenerateNewImpl:
    async def test_no_sid_emits_nothing(self, pool):
        emit, events = recording_emit()

        await generate_new_impl({"sid": ""}, emit=emit, pool=pool)

        assert events == []

    async def test_no_profile_emits_error(self, pool):
        emit, events = recording_emit()

        await generate_new_impl(
            _base_data(profile_id=None),
            emit=emit,
            pool=pool,
        )

        assert len(events) == 1
        assert events[0].event == "generate_error"
        assert "Profile not found" in events[0].data["error_message"]

    async def test_no_session_emits_error(self, pool):
        emit, events = recording_emit()

        await generate_new_impl(
            _base_data(session_id=None),
            emit=emit,
            pool=pool,
        )

        assert len(events) == 1
        assert events[0].event == "generate_error"
        assert "Session not found" in events[0].data["error_message"]

    async def test_invalid_profile_id_emits_error(self, pool):
        emit, events = recording_emit()

        await generate_new_impl(
            _base_data(profile_id="not-a-uuid"),
            emit=emit,
            pool=pool,
        )

        assert len(events) == 1
        assert events[0].event == "generate_error"
        assert "Invalid profile_id" in events[0].data["error_message"]

    async def test_normal_forwards_to_prepare(self, pool):
        emit, events = recording_emit()
        data = _base_data()

        await generate_new_impl(data, emit=emit, pool=pool)

        assert len(events) == 1
        assert events[0].event == "generate_prepare"
        assert events[0].data == data

    async def test_rate_limit_exceeded_emits_error(self, pool, redis_client):
        async with pool.acquire() as conn:
            profile = await create_profile(conn, redis_client)
            session = await create_session(conn, profile_id=profile.id)
            group = await create_group(conn, session_id=session.id)
            for _ in range(2):
                await create_run(
                    conn,
                    group_id=group.id,
                    session_id=session.id,
                    profiles_id=profile.id,
                )
            await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY runs_mv")

        emit, events = recording_emit()
        await generate_new_impl(
            _base_data(
                profile_id=str(profile.id),
                session_id=str(session.id),
                requests_per_day=1,
            ),
            emit=emit,
            pool=pool,
        )

        assert len(events) == 1
        assert events[0].event == "generate_error"
        assert "Rate limit exceeded" in events[0].data["error_message"]

    async def test_rate_limit_ok_forwards_to_prepare(self, pool, redis_client):
        async with pool.acquire() as conn:
            profile = await create_profile(conn, redis_client)
            session = await create_session(conn, profile_id=profile.id)
            await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY runs_mv")

        emit, events = recording_emit()
        await generate_new_impl(
            _base_data(
                profile_id=str(profile.id),
                session_id=str(session.id),
                requests_per_day=5,
            ),
            emit=emit,
            pool=pool,
        )

        assert len(events) == 1
        assert events[0].event == "generate_prepare"

    async def test_rate_limit_audio_session_emits_error_and_complete(
        self, pool, redis_client
    ):
        async with pool.acquire() as conn:
            profile = await create_profile(conn, redis_client)
            session = await create_session(conn, profile_id=profile.id)
            group = await create_group(conn, session_id=session.id)
            for _ in range(2):
                await create_run(
                    conn,
                    group_id=group.id,
                    session_id=session.id,
                    profiles_id=profile.id,
                )
            await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY runs_mv")

        create_audio_session(
            sid="s1",
            chat_id="c1",
            run_id="run-1",
            group_id=str(group.id),
        )

        emit, events = recording_emit()
        await generate_new_impl(
            _base_data(
                profile_id=str(profile.id),
                session_id=str(session.id),
                group_id=str(group.id),
                requests_per_day=1,
            ),
            emit=emit,
            pool=pool,
        )

        assert len(events) == 2
        assert events[0].event == "attempt_error"
        assert events[0].data["error_type"] == "rate_limit"
        assert events[0].data["chat_id"] == "c1"
        assert events[1].event == "generate_audio_session_complete"

    async def test_audio_continuation_rotates_run_id(self, pool):
        emit, events = recording_emit()
        session = create_audio_session(
            sid="s1",
            chat_id="c1",
            run_id="run-1",
            group_id="g1",
        )

        await generate_new_impl(
            _base_data(group_id="g1"),
            emit=emit,
            pool=pool,
        )

        assert events == []
        assert session.run_id != "run-1"
        assert get_session_by_group_id("g1") is session
        assert get_session_by_run_id(session.run_id) is session
        assert get_session_by_run_id("run-1") is None
