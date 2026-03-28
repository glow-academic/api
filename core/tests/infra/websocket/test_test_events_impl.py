"""Tests for test_events_impl — compatibility re-export module."""

from __future__ import annotations

import inspect

import pytest

from app.infra.websocket.test_events_impl import (
    _extract_grade_feedback,
    _extract_grade_passed,
    _extract_grade_score,
    _find_next_run_id,
    test_error_impl,
    test_grade_complete_impl,
    test_group_impl,
    test_next_impl,
    test_proceed_impl,
    test_progress_impl,
    test_run_done_impl,
    test_run_impl,
    test_start_impl,
)

pytestmark = pytest.mark.asyncio


async def test_extract_grade_score_from_tool_results():
    """_extract_grade_score extracts score from tool result list."""
    results = [{"result": {"score": 88}}]
    score = _extract_grade_score(results)
    assert score == 88


async def test_extract_grade_score_returns_none_for_empty():
    """_extract_grade_score returns None when no score present."""
    score = _extract_grade_score([])
    assert score is None


async def test_extract_grade_score_uses_total_fallback():
    """_extract_grade_score falls back to 'total' field."""
    results = [{"result": {"total": 75}}]
    score = _extract_grade_score(results)
    assert score == 75


async def test_extract_grade_passed_true():
    """_extract_grade_passed returns True from tool results."""
    results = [{"result": {"passed": True}}]
    passed = _extract_grade_passed(results)
    assert passed is True


async def test_extract_grade_passed_false():
    """_extract_grade_passed returns False from tool results."""
    results = [{"result": {"passed": False}}]
    passed = _extract_grade_passed(results)
    assert passed is False


async def test_extract_grade_passed_returns_none_for_missing():
    """_extract_grade_passed returns None when not present."""
    passed = _extract_grade_passed([{"result": {}}])
    assert passed is None


async def test_extract_grade_feedback():
    """_extract_grade_feedback extracts feedback string."""
    results = [{"result": {"feedback": "Well done"}}]
    feedback = _extract_grade_feedback(results)
    assert feedback == "Well done"


async def test_extract_grade_feedback_returns_none_for_missing():
    """_extract_grade_feedback returns None when feedback is missing."""
    feedback = _extract_grade_feedback([{"result": {}}])
    assert feedback is None


async def test_re_exports_are_async_callables():
    """All re-exported workflow functions are async callables."""
    for fn in [
        test_start_impl,
        test_run_impl,
        test_next_impl,
        test_progress_impl,
        test_run_done_impl,
        test_grade_complete_impl,
        test_proceed_impl,
        test_error_impl,
        test_group_impl,
    ]:
        assert inspect.iscoroutinefunction(fn), f"{fn.__name__} should be async"
