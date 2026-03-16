"""Focused tests for canonical workflow internal entrypoints."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.infra.websocket.socket_event import internal_event, recording_emit
from app.infra.attempt.start import (
    attempt_start_internal_impl as run_attempt_start_internal,
)
from app.infra.attempt.grade import (
    attempt_grade_internal_impl as run_attempt_grade_internal,
)
from app.infra.test.start import (
    test_start_internal_impl as run_test_start_internal,
)

pytestmark = pytest.mark.asyncio


async def test_attempt_start_internal_impl_returns_terminal_result(monkeypatch) -> None:
    async def _start_impl(
        data,
        *,
        emit,
        pool,
        redis,
        profile_id,
        session_id,
    ) -> None:
        del data, pool, redis, profile_id, session_id
        await emit(
            [
                internal_event(
                    "attempt_proceed",
                    {
                        "attempt_id": "attempt-1",
                        "group_id": str(uuid4()),
                    },
                )
            ]
        )

    async def _proceed_impl(data, *, emit) -> None:
        del data
        await emit(
            [
                internal_event(
                    "attempt_chat_started",
                    {
                        "attempt_id": "attempt-1",
                        "chat_id": "attempt-chat-1",
                    },
                )
            ]
        )

    monkeypatch.setattr(
        "app.infra.attempt.start.attempt_start_impl",
        _start_impl,
    )
    monkeypatch.setattr(
        "app.infra.attempt.proceed.attempt_proceed_internal_impl",
        _proceed_impl,
    )
    monkeypatch.setattr(
        "app.infra.attempt.start.get_pool",
        lambda: object(),
    )
    monkeypatch.setattr(
        "app.infra.attempt.start.get_redis_client",
        lambda: object(),
    )

    emit, recorded = recording_emit()
    result = await run_attempt_start_internal(
        {
            "sid": "socket-1",
            "profile_id": str(uuid4()),
            "session_id": str(uuid4()),
            "home_id": str(uuid4()),
            "infinite_mode": False,
        },
        emit=emit,
        audit=False,
    )

    assert result.attempt_id == "attempt-1"
    assert result.attempt_chat_id == "attempt-chat-1"
    assert [event.event for event in recorded] == [
        "attempt_proceed",
        "attempt_chat_started",
    ]


async def test_test_start_internal_impl_returns_terminal_result(monkeypatch) -> None:
    async def _resolve_identity(pool, profile_id, redis, *, session_id):
        del pool, profile_id, redis, session_id
        return SimpleNamespace(profiles_id=uuid4())

    async def _start_impl(data, *, emit, pool, redis) -> None:
        del data, pool, redis
        await emit(
            [
                internal_event(
                    "test_proceed",
                    {
                        "test_id": "test-1",
                    },
                )
            ]
        )

    async def _proceed_impl(data, *, emit) -> None:
        del data
        await emit(
            [
                internal_event(
                    "test_invocation_started",
                    {
                        "test_id": "test-1",
                        "test_invocation_id": "invocation-1",
                    },
                )
            ]
        )

    monkeypatch.setattr(
        "app.infra.test.start.resolve_profile_identity_context",
        _resolve_identity,
    )
    monkeypatch.setattr(
        "app.infra.test.start.test_start_impl",
        _start_impl,
    )
    monkeypatch.setattr(
        "app.infra.test.start.test_proceed_internal_impl",
        _proceed_impl,
    )
    monkeypatch.setattr(
        "app.infra.test.start.get_pool",
        lambda: object(),
    )
    monkeypatch.setattr(
        "app.infra.test.start.get_redis_client",
        lambda: object(),
    )

    emit, recorded = recording_emit()
    result = await run_test_start_internal(
        {
            "sid": "socket-1",
            "profile_id": str(uuid4()),
            "session_id": str(uuid4()),
            "benchmark_id": str(uuid4()),
            "infinite_mode": False,
        },
        emit=emit,
        audit=False,
    )

    assert result.test_id == "test-1"
    assert result.invocation_id == "invocation-1"
    assert [event.event for event in recorded] == [
        "test_proceed",
        "test_invocation_started",
    ]


async def test_attempt_grade_internal_impl_emits_grade_complete(monkeypatch) -> None:
    class _Acquire:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _Pool:
        def acquire(self):
            return _Acquire()

    async def _resolve_identity(pool, profile_id, redis, *, session_id):
        del pool, profile_id, redis, session_id
        return SimpleNamespace(profiles_id=uuid4())

    async def _create_group(conn, *, session_id):
        del conn, session_id
        return SimpleNamespace(id=uuid4())

    async def _create_run(conn, *, session_id, group_id, profiles_id):
        del conn, session_id, group_id, profiles_id
        return SimpleNamespace(id=uuid4())

    async def _create_call(conn, *, run_id, session_id):
        del conn, run_id, session_id
        return SimpleNamespace(id=uuid4())

    async def _create_attempt_grade(conn, *, chat_id, call_id, run_id, time_taken, passed, score):
        del conn, chat_id, call_id, run_id, time_taken, passed, score
        return SimpleNamespace(id=uuid4())

    monkeypatch.setattr(
        "app.infra.attempt.grade.resolve_profile_identity_context",
        _resolve_identity,
    )
    monkeypatch.setattr(
        "app.infra.attempt.grade.create_group",
        _create_group,
    )
    monkeypatch.setattr(
        "app.infra.attempt.grade.create_run",
        _create_run,
    )
    monkeypatch.setattr(
        "app.infra.attempt.grade.create_call",
        _create_call,
    )
    monkeypatch.setattr(
        "app.infra.attempt.grade.create_attempt_grade",
        _create_attempt_grade,
    )
    monkeypatch.setattr(
        "app.infra.attempt.grade.get_pool",
        lambda: _Pool(),
    )
    monkeypatch.setattr(
        "app.infra.attempt.grade.get_redis_client",
        lambda: object(),
    )

    emit, recorded = recording_emit()
    result = await run_attempt_grade_internal(
        {
            "sid": "socket-1",
            "profile_id": str(uuid4()),
            "session_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "chat_id": str(uuid4()),
        },
        emit=emit,
        audit=False,
    )

    assert result.grade_id is not None
    assert [event.event for event in recorded[:2]] == [
        "attempt_grade_start",
        "attempt_grade_complete",
    ]
