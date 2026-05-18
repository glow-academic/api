"""Tests for benchmark permissions — compute_benchmark_eval_status."""

import pytest

from app.infra.benchmark.permissions import compute_benchmark_eval_status

pytestmark = pytest.mark.asyncio


async def test_passed_when_has_passed_is_true():
    result = compute_benchmark_eval_status(
        has_passed=True, completed_invocations=5, total_invocations=10
    )
    assert result == "passed"


async def test_in_progress_when_completed_invocations_present():
    result = compute_benchmark_eval_status(
        has_passed=False, completed_invocations=3, total_invocations=10
    )
    assert result == "in-progress"


async def test_in_progress_when_total_invocations_nonzero():
    result = compute_benchmark_eval_status(
        has_passed=False, completed_invocations=0, total_invocations=5
    )
    assert result == "in-progress"


async def test_not_started_when_no_invocations():
    result = compute_benchmark_eval_status(
        has_passed=False, completed_invocations=0, total_invocations=0
    )
    assert result == "not-started"


async def test_passed_takes_priority_over_completed():
    """Even if completed < total, has_passed=True means 'passed'."""
    result = compute_benchmark_eval_status(
        has_passed=True, completed_invocations=1, total_invocations=10
    )
    assert result == "passed"
