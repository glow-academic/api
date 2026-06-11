"""Tests for active websocket run/result/connection helpers."""

import pytest

import app.infra.globals as globals_mod
from app.infra.websocket.cancel_active_result import cancel_active_result
from app.infra.websocket.cancel_active_run import cancel_active_run
from app.infra.websocket.find_chat_by_socket import find_chat_by_socket
from app.infra.websocket.find_chats_by_socket import find_chats_by_socket
from app.infra.websocket.get_active_connection import get_active_connection
from app.infra.websocket.get_active_run import get_active_run
from app.infra.websocket.remove_active_connection import remove_active_connection
from app.infra.websocket.remove_active_result import remove_active_result
from app.infra.websocket.remove_active_run import remove_active_run
from app.infra.websocket.set_active_connection import set_active_connection
from app.infra.websocket.set_active_run import set_active_run
from app.infra.websocket.store_active_events import store_active_events
from app.infra.websocket.store_active_result import store_active_result
from app.infra.websocket.store_active_run import store_active_run


@pytest.fixture
def websocket_runtime(redis_client):
    """Bind real Redis and reset in-memory active result state."""
    original_redis = globals_mod.redis_client
    globals_mod.redis_client = redis_client
    globals_mod.active_results.clear()
    try:
        yield redis_client
    finally:
        globals_mod.redis_client = original_redis
        globals_mod.active_results.clear()


class RecordingResult:
    def __init__(self):
        self.cancelled = False

    async def cancel(self) -> None:
        self.cancelled = True


class RecordingEvents:
    def __init__(self):
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class TestActiveRunHelpers:
    @pytest.mark.asyncio
    async def test_set_get_cancel_and_remove_active_run(self, websocket_runtime):
        await set_active_run("chat-1", "run-1")

        assert await get_active_run("chat-1") == "run-1"
        assert await cancel_active_run("chat-1") is True
        assert await websocket_runtime.get("cancel_run:run-1") == b"1"

        await remove_active_run("chat-1")
        assert await get_active_run("chat-1") is None

    @pytest.mark.asyncio
    async def test_store_active_run_persists_generated_run_id(self, websocket_runtime):
        await store_active_run("chat-2", object())

        run_id = await get_active_run("chat-2")
        assert run_id is not None
        assert len(run_id) == 36

    @pytest.mark.asyncio
    async def test_cancel_active_run_returns_false_without_run(self, websocket_runtime):
        assert await cancel_active_run("missing-chat") is False


class TestActiveResultHelpers:
    @pytest.mark.asyncio
    async def test_store_cancel_and_remove_active_result(self, websocket_runtime):
        result = RecordingResult()
        events = RecordingEvents()

        await store_active_result("chat-4", result)
        await store_active_events("chat-4", events)

        assert await cancel_active_result("chat-4") is True
        assert result.cancelled is True
        assert events.closed is True

        await remove_active_result("chat-4")
        assert globals_mod.active_results == {}

    @pytest.mark.asyncio
    async def test_cancel_active_result_returns_false_when_missing(
        self, websocket_runtime
    ):
        assert await cancel_active_result("missing-chat") is False

    @pytest.mark.asyncio
    async def test_cancel_active_result_handles_sync_cancel(self, websocket_runtime):
        class SyncResult:
            def __init__(self):
                self.cancelled = False

            def cancel(self) -> None:
                self.cancelled = True

        result = SyncResult()
        await store_active_result("chat-5", result)

        assert await cancel_active_result("chat-5") is True
        assert result.cancelled is True


class TestActiveConnectionHelpers:
    @pytest.mark.asyncio
    async def test_set_get_find_and_remove_active_connection(self, websocket_runtime):
        await set_active_connection("chat-6", "sid-a")
        await set_active_connection("chat-6", "sid-b")
        await set_active_connection("chat-7", "sid-b")

        first_sid = await get_active_connection("chat-6")
        assert first_sid in {"sid-a", "sid-b"}
        assert await find_chat_by_socket("sid-a") == "chat-6"
        assert sorted(await find_chats_by_socket("sid-b")) == ["chat-6", "chat-7"]

        await remove_active_connection("chat-6", "sid-a")
        assert await websocket_runtime.smembers("active_connection:chat-6") == {
            b"sid-b"
        }

        await remove_active_connection("chat-6", "sid-b")
        assert await websocket_runtime.exists("active_connection:chat-6") == 0

    @pytest.mark.asyncio
    async def test_find_chats_by_socket_uses_reverse_index_no_scan(
        self, websocket_runtime, monkeypatch
    ):
        """PERF2: with the reverse index populated, disconnect lookup must be
        a direct O(1) SMEMBERS — NO unbounded keyspace SCAN."""
        # Populate several chats for one socket plus unrelated chats that an
        # old SCAN would have to walk.
        await set_active_connection("chat-a", "sid-x")
        await set_active_connection("chat-b", "sid-x")
        for i in range(20):
            await set_active_connection(f"noise-{i}", f"other-{i}")

        # Any scan_iter during the lookup is a regression.
        def _no_scan(*args, **kwargs):
            raise AssertionError(
                "find_chats_by_socket issued a SCAN despite a populated "
                "reverse index (PERF2 regression)"
            )

        monkeypatch.setattr(websocket_runtime, "scan_iter", _no_scan)

        chats = await find_chats_by_socket("sid-x")
        assert sorted(chats) == ["chat-a", "chat-b"]

        # Singular finder also avoids the scan.
        assert await find_chat_by_socket("sid-x") in {"chat-a", "chat-b"}

    @pytest.mark.asyncio
    async def test_remove_active_connection_prunes_reverse_index(
        self, websocket_runtime
    ):
        """Removing a connection drops it from the reverse index so a later
        disconnect lookup returns only still-active chats."""
        await set_active_connection("chat-c", "sid-y")
        await set_active_connection("chat-d", "sid-y")
        assert sorted(await find_chats_by_socket("sid-y")) == ["chat-c", "chat-d"]

        await remove_active_connection("chat-c", "sid-y")
        assert await find_chats_by_socket("sid-y") == ["chat-d"]
        assert await websocket_runtime.smembers("socket_chats:sid-y") == {b"chat-d"}
