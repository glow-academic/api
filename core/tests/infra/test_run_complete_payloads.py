"""Tests for extracted pure helpers in run_complete_impl."""

import uuid
from contextlib import asynccontextmanager

import pytest

from app.infra.websocket import run_complete_impl as rc_module
from app.infra.websocket.run_complete_impl import (
    _table_name,
    build_run_complete_payload,
    run_complete_impl,
)


def test_table_name_uses_resource_suffix():
    assert _table_name("resource", "names") == "names_resource"


def test_table_name_uses_entry_suffix():
    assert _table_name("entry", "contents") == "contents_entry"


def test_build_run_complete_payload_serializes_generation_complete_shape():
    payload = build_run_complete_payload(
        sid="sid-1",
        artifact_type="chat",
        group_id="group-1",
        run_id="run-1",
    )

    assert payload == {
        "type": "complete",
        "sid": "sid-1",
        "artifact_type": "chat",
        "group_id": "group-1",
        "run_id": "run-1",
        "success": True,
        "message": "Chat generation completed",
        "artifact_id": None,
        "tool_results": None,
        "metadata": None,
    }


class _FakeConn:
    """Minimal asyncpg.Connection stand-in: only ``transaction()`` is used by
    run_complete_impl's turn-write block (the nested create_* impls are stubbed)."""

    @asynccontextmanager
    async def transaction(self):
        yield


@pytest.mark.asyncio
async def test_run_complete_threads_cached_input_tokens_to_create_token(monkeypatch):
    """C1: cache-read tokens carried on the run_complete payload must reach
    ``create_token(cached_input_tokens=…)`` — they used to be dropped, so the
    cached portion of spend was billed as $0 and no pricing_type='cached' row
    could be derived (runs_mv reads tokens_entry.cached_input_tokens)."""
    captured: dict[str, object] = {}

    async def _fake_create_token(_conn, _redis, **kwargs):
        captured.update(kwargs)

    # Short-circuit after the turn write so no real DB/coordination is needed.
    async def _fake_resolve(*_a, **_k):
        raise AssertionError("should not reach completion coordination")

    monkeypatch.setattr(rc_module, "create_token", _fake_create_token)
    # No assistant/reasoning text → persist_run_message is not called.

    run_id = uuid.uuid4()
    session_id = uuid.uuid4()

    # group_id omitted so the impl returns right after the (stubbed) turn write,
    # before resolve_run_completion — keeps this a pure no-DB unit test.
    monkeypatch.setattr(rc_module, "resolve_run_completion", _fake_resolve)

    await run_complete_impl(
        {
            "sid": "sid-cached",
            "run_id": str(run_id),
            "session_id": str(session_id),
            "artifact_type": "persona",
            "modality": "text",
            "input_text_tokens": 100,
            "output_text_tokens": 20,
            "cached_input_tokens": 50000,
        },
        emit=None,  # never invoked on this no-group path
        conn=_FakeConn(),
        redis=None,
        upload_folder=None,
    )

    assert captured["input_tokens"] == 100
    assert captured["output_tokens"] == 20
    assert captured["cached_input_tokens"] == 50000
