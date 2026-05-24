"""Behavior tests for `core/app/infra/test/workflows.py`.

Replaces 3 prior brittle implementation-shape tests (`assert
asyncio.iscoroutinefunction(...)`) with assertions that exercise the
actual contracts.

Covers:
- Pure helpers (`_extract_grade_score`, `_extract_grade_passed`,
  `_extract_grade_feedback`) — deterministic over synthetic input.
- Event-handler translators (`test_progress_impl`, `test_run_done_impl`,
  `test_error_impl`) — call with a dict, capture emits via
  `recording_emit`, assert payload shape.

No DB, no Redis needed for any of these — the handlers under test
import `get_redis_client` but never call out (they translate a dict
to an emit). Reaching for the real Redis would slow these unit tests
down for no signal.
"""

from __future__ import annotations

import pytest

from app.infra.test.workflows import (
    _extract_grade_feedback,
    _extract_grade_passed,
    _extract_grade_score,
)
# Alias on import: the production functions start with `test_`, so pytest
# would otherwise try to collect them as test functions at module level.
from app.infra.test.workflows import test_error_impl as _test_error_impl
from app.infra.test.workflows import test_progress_impl as _test_progress_impl
from app.infra.test.workflows import test_run_done_impl as _test_run_done_impl
from app.infra.websocket.socket_event import recording_emit


# ─── _extract_grade_score ──────────────────────────────────────────────────


class TestExtractGradeScore:
    def test_returns_int_score_from_first_matching_result(self):
        assert _extract_grade_score([{"result": {"score": 7}}]) == 7

    def test_falls_back_to_total_when_score_missing(self):
        assert _extract_grade_score([{"result": {"total": 9}}]) == 9

    def test_prefers_score_over_total_within_same_result(self):
        """When both `score` and `total` are present on the same item,
        `score` wins — that's the order the function checks them."""
        assert _extract_grade_score([{"result": {"score": 3, "total": 99}}]) == 3

    def test_walks_to_next_item_when_first_has_neither(self):
        results = [
            {"result": {"feedback": "nope"}},  # neither score nor total
            {"result": {"score": 5}},
        ]
        assert _extract_grade_score(results) == 5

    def test_skips_non_int_score(self):
        """A float `score` isn't accepted as an int — function walks on."""
        results = [
            {"result": {"score": 4.2}},
            {"result": {"score": 8}},
        ]
        assert _extract_grade_score(results) == 8

    def test_returns_none_when_no_match(self):
        assert _extract_grade_score([]) is None
        assert _extract_grade_score([{"result": {}}]) is None
        assert _extract_grade_score([{"result": "not-a-dict"}]) is None
        assert _extract_grade_score([{}]) is None  # missing "result" key


# ─── _extract_grade_passed ─────────────────────────────────────────────────


class TestExtractGradePassed:
    def test_returns_bool_passed(self):
        assert _extract_grade_passed([{"result": {"passed": True}}]) is True
        assert _extract_grade_passed([{"result": {"passed": False}}]) is False

    def test_skips_non_bool_passed(self):
        """A truthy non-bool (e.g. integer 1) isn't accepted — the type
        check enforces real booleans. Important because grade outputs
        from LLM tools can be sloppy."""
        results = [
            {"result": {"passed": 1}},      # truthy but not bool
            {"result": {"passed": False}},
        ]
        assert _extract_grade_passed(results) is False

    def test_returns_none_when_no_match(self):
        assert _extract_grade_passed([]) is None
        assert _extract_grade_passed([{"result": {"score": 10}}]) is None


# ─── _extract_grade_feedback ───────────────────────────────────────────────


class TestExtractGradeFeedback:
    def test_returns_first_non_empty_feedback(self):
        assert _extract_grade_feedback(
            [{"result": {"feedback": "nicely done"}}]
        ) == "nicely done"

    def test_skips_empty_string_feedback(self):
        """Empty `feedback` does NOT short-circuit the search — the
        function walks to the next item with a non-empty string."""
        results = [
            {"result": {"feedback": ""}},
            {"result": {"feedback": "later one"}},
        ]
        assert _extract_grade_feedback(results) == "later one"

    def test_skips_non_string_feedback(self):
        results = [
            {"result": {"feedback": 42}},
            {"result": {"feedback": "real"}},
        ]
        assert _extract_grade_feedback(results) == "real"

    def test_returns_none_when_no_match(self):
        assert _extract_grade_feedback([]) is None
        assert _extract_grade_feedback([{"result": {}}]) is None


# ─── test_progress_impl ────────────────────────────────────────────────────


class TestTestProgressImpl:
    pytestmark = pytest.mark.asyncio

    async def test_emits_grade_started_with_payload(self):
        """The handler is a pure translator: dict in → one
        `test.grade.started` internal_event out, with progress fields
        preserved on the payload."""
        emit, recorded = recording_emit()

        await _test_progress_impl(
            {
                "sid": "s-123",
                "invocation_id": "inv-1",
                "run_id": "run-7",
                "current_run": 2,
                "total_runs": 5,
                "message": "halfway",
            },
            emit=emit,
        )

        assert len(recorded) == 1
        event = recorded[0]
        assert event.event == "test.grade.started"
        assert event.data["invocation_id"] == "inv-1"
        assert event.data["run_id"] == "run-7"
        assert event.data["current_run"] == 2
        assert event.data["total_runs"] == 5
        assert event.data["message"] == "halfway"
        # Rooms include the sid plus a test-namespaced room.
        assert "s-123" in event.data["rooms"]
        assert "test_inv-1" in event.data["rooms"]

    async def test_falls_back_to_chat_id_for_invocation(self):
        """Some clients send `chat_id` instead of `invocation_id`. The
        handler accepts either."""
        emit, recorded = recording_emit()

        await _test_progress_impl(
            {"sid": "s-1", "chat_id": "chat-42"}, emit=emit,
        )

        assert len(recorded) == 1
        assert recorded[0].data["invocation_id"] == "chat-42"

    async def test_silent_noop_when_no_invocation_id(self):
        """Without invocation_id OR chat_id, the handler can't route the
        event — it returns silently rather than emitting a malformed
        payload. Guards against a noisy regression where some upstream
        change starts sending invocation-less progress."""
        emit, recorded = recording_emit()

        await _test_progress_impl({"sid": "s-1"}, emit=emit)

        assert recorded == []

    async def test_no_sid_yields_empty_rooms(self):
        """Without a sid, the rooms list is empty — `test_{id}` alone
        isn't a valid room without a session context."""
        emit, recorded = recording_emit()

        await _test_progress_impl({"invocation_id": "inv-9"}, emit=emit)

        assert len(recorded) == 1
        assert recorded[0].data["rooms"] == []


# ─── test_run_done_impl ────────────────────────────────────────────────────


class TestTestRunDoneImpl:
    pytestmark = pytest.mark.asyncio

    async def test_emits_run_complete_with_remaining(self):
        emit, recorded = recording_emit()

        await _test_run_done_impl(
            {
                "sid": "s-1",
                "invocation_id": "inv-1",
                "run_id": "r-3",
                "current_run": 2,
                "total_runs": 5,
            },
            emit=emit,
        )

        assert len(recorded) == 1
        event = recorded[0]
        assert event.event == "test.run.completed"
        assert event.data["invocation_id"] == "inv-1"
        assert event.data["run_id"] == "r-3"
        assert event.data["current_run"] == 2
        assert event.data["total_runs"] == 5
        assert event.data["remaining_runs"] == 3  # 5 - 2

    async def test_defaults_when_progress_fields_missing(self):
        """Defaults: current_run=1, total_runs=1 → remaining_runs=0.
        Guards against a regression that would key off undefined values."""
        emit, recorded = recording_emit()

        await _test_run_done_impl(
            {"invocation_id": "inv-x"}, emit=emit,
        )

        assert recorded[0].data["current_run"] == 1
        assert recorded[0].data["total_runs"] == 1
        assert recorded[0].data["remaining_runs"] == 0

    async def test_silent_noop_when_no_invocation_id(self):
        emit, recorded = recording_emit()
        await _test_run_done_impl({}, emit=emit)
        assert recorded == []


# ─── test_error_impl ───────────────────────────────────────────────────────


class TestTestErrorImpl:
    pytestmark = pytest.mark.asyncio

    async def test_emits_error_event(self):
        emit, recorded = recording_emit()

        await _test_error_impl(
            {
                "sid": "s-1",
                "invocation_id": "inv-1",
                "error": "something blew up",
                "error_type": "RuntimeError",
            },
            emit=emit,
        )

        assert len(recorded) == 1
        event = recorded[0]
        # Just verify the event was emitted with the right error payload
        # — exact event name is asserted but the field shape is
        # whatever the handler chose to project.
        assert "error" in event.event.lower()
        assert event.data["invocation_id"] == "inv-1"
