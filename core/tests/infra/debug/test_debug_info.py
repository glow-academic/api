"""Tests for debug info helper."""

from types import SimpleNamespace

import pytest

from app.infra.debug.debug_info import debug_info, extract_debug_context


class FakeConn:
    def __init__(self) -> None:
        self.calls: list[tuple[object, str]] = []

    async def execute(self, query: str, run_id: object, content: str) -> None:
        self.calls.append((run_id, content))


class FailingConn:
    async def execute(self, query: str, run_id: object, content: str) -> None:
        raise RuntimeError("db is down")


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
async def test_debug_info_persists_before_returning():
    # The insert must have completed by the time debug_info returns its
    # confirmation — no event-loop yield (asyncio.sleep) is needed. If the
    # insert were fire-and-forget (un-awaited create_task), conn.calls would
    # still be empty here and the un-retained task could be GC'd entirely.
    conn = FakeConn()

    result = await debug_info({"run_id": "run-1", "conn": conn}, "need help")

    assert conn.calls == [("run-1", "need help")]
    assert result == "Saved debug info"


@pytest.mark.asyncio
async def test_debug_info_surfaces_insert_failure():
    # A failing insert must surface as an error rather than being swallowed:
    # awaiting the coroutine lets the except clause catch it. With a
    # fire-and-forget create_task the try/except only guards task *creation*,
    # so a DB failure would be silently lost and the caller still told
    # "Saved debug info".
    result = await debug_info({"run_id": "run-1", "conn": FailingConn()}, "need help")

    assert result.startswith("Error saving problem:")
    assert "db is down" in result
