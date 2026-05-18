"""Tests for debug info helper."""

import asyncio
from types import SimpleNamespace

import pytest

from app.infra.debug.debug_info import debug_info, extract_debug_context


class FakeConn:
    def __init__(self) -> None:
        self.calls: list[tuple[object, str]] = []

    async def execute(self, query: str, run_id: object, content: str) -> None:
        self.calls.append((run_id, content))


def test_extract_debug_context_supports_multiple_shapes():
    conn = object()

    assert extract_debug_context({"run_id": "r1", "conn": conn}) == ("r1", conn)
    assert extract_debug_context(SimpleNamespace(run_id="r2", conn=conn)) == (
        "r2",
        conn,
    )
    nested = SimpleNamespace(context=SimpleNamespace(run_id="r3", conn=conn))
    assert extract_debug_context(nested) == ("r3", conn)


@pytest.mark.asyncio
async def test_debug_info_returns_error_when_context_is_missing():
    result = await debug_info({}, "blocked")

    assert result == "Error: Missing run_id or conn in context"


@pytest.mark.asyncio
async def test_debug_info_schedules_problem_insert():
    conn = FakeConn()

    result = await debug_info({"run_id": "run-1", "conn": conn}, "need help")
    await asyncio.sleep(0)

    assert result == "Saved debug info"
    assert conn.calls == [("run-1", "need help")]
