"""Focused tests for canonical workflow internal entrypoints."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.infra.websocket.socket_event import internal_event, recording_emit
from app.infra.test.start import (
    test_start_internal_impl as run_test_start_internal,
)

pytestmark = pytest.mark.asyncio


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
