"""Tests for home_permissions — re-exported chat permission helpers."""

import pytest

from app.infra.home_permissions import (
    compute_completion_pct,
    compute_mode,
    compute_pass_pct,
    compute_score_status,
    compute_show_continue,
    compute_show_view,
    compute_status,
    compute_status_instructional,
    format_cohort_names,
)

pytestmark = pytest.mark.asyncio


async def test_compute_mode_practice():
    assert compute_mode(practice=True) == "practice"


async def test_compute_mode_member():
    assert compute_mode(practice=False, user_role="member") == "member"


async def test_compute_mode_instructional():
    assert compute_mode(practice=False, user_role="admin") == "instructional"


async def test_compute_score_status_high():
    assert compute_score_status(85.0) == "high"


async def test_compute_score_status_none():
    assert compute_score_status(None) is None


async def test_compute_pass_pct_normal():
    assert compute_pass_pct(100, 70) == 70


async def test_compute_pass_pct_zero_total():
    assert compute_pass_pct(0, 70) is None


async def test_compute_status_passed():
    assert compute_status(has_passed=True, completed_count=1) == "passed"


async def test_compute_status_not_started():
    assert compute_status(has_passed=False, completed_count=0) == "not-started"


async def test_compute_status_instructional_all_passed():
    assert compute_status_instructional(5, 0, 5) == "passed"


async def test_compute_completion_pct_half():
    assert compute_completion_pct(3, 2, 10) == 50


async def test_format_cohort_names_three():
    result = format_cohort_names(["C", "A", "B"])
    assert result == "A, B, and C"


async def test_compute_show_view_not_archived():
    assert compute_show_view(is_archived=False) is True


async def test_compute_show_continue_archived():
    assert compute_show_continue(
        is_archived=True, infinite_mode=False,
        num_scenarios=5, num_scenarios_completed=0,
        time_limit_seconds=None, elapsed_seconds=None,
        num_incomplete_chats=None,
    ) is False
