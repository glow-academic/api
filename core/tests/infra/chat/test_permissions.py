"""Tests for chat permissions — pure business logic functions."""

import pytest

from app.infra.attempt.chat.permissions import (
    compute_bundle_section_show,
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


# --- compute_mode ---


async def test_compute_mode_returns_practice_when_practice_true():
    assert compute_mode(practice=True) == "practice"
    assert compute_mode(practice=True, role_level=1) == "practice"


async def test_compute_mode_returns_instructional_for_elevated_roles():
    # Preferred: use role_level
    assert compute_mode(practice=False, role_level=0) == "instructional"  # Super Administrator
    assert compute_mode(practice=False, role_level=1) == "instructional"  # Administrator
    assert compute_mode(practice=False, role_level=2) == "instructional"  # Instructional Staff


async def test_compute_mode_returns_member_for_regular_roles():
    # Preferred: use role_level
    assert compute_mode(practice=False, role_level=3) == "member"  # GTA/UTA
    assert compute_mode(practice=False, role_level=4) == "member"  # Guest
    assert compute_mode(practice=False, role_level=99) == "member"  # default


async def test_compute_mode_legacy_string_fallback():
    """Legacy string-based role names still work when role_level is not provided."""
    assert compute_mode(practice=False, user_role="instructional") == "instructional"
    assert compute_mode(practice=False, user_role="admin") == "instructional"
    assert compute_mode(practice=False, user_role="superadmin") == "instructional"
    assert compute_mode(practice=False, user_role="Instructional Staff") == "instructional"
    assert compute_mode(practice=False, user_role="Administrator") == "instructional"
    assert compute_mode(practice=False, user_role="Super Administrator") == "instructional"
    assert compute_mode(practice=False, user_role="member") == "member"
    assert compute_mode(practice=False, user_role=None) == "member"
    assert compute_mode(practice=False, user_role="guest") == "member"


# --- compute_score_status ---


async def test_compute_score_status_returns_none_for_none():
    assert compute_score_status(None) is None


async def test_compute_score_status_high_medium_low():
    assert compute_score_status(80.0) == "high"
    assert compute_score_status(70.0) == "high"
    assert compute_score_status(50.0) == "medium"
    assert compute_score_status(40.0) == "medium"
    assert compute_score_status(30.0) == "low"
    assert compute_score_status(0.0) == "low"


async def test_compute_score_status_custom_threshold():
    assert compute_score_status(60.0, pass_threshold=50.0) == "high"
    assert compute_score_status(45.0, pass_threshold=50.0) == "medium"


# --- compute_pass_pct ---


async def test_compute_pass_pct_calculates_percentage():
    assert compute_pass_pct(100, 70) == 70
    assert compute_pass_pct(200, 150) == 75


async def test_compute_pass_pct_returns_none_for_zero_total():
    assert compute_pass_pct(0, 50) is None
    assert compute_pass_pct(None, 50) is None


async def test_compute_pass_pct_returns_none_for_none_pass():
    assert compute_pass_pct(100, None) is None


async def test_compute_pass_pct_clamps_when_pass_exceeds_total():
    # R9: a misconfigured rubric (pass_points > total_points) must not yield a
    # >100% pass threshold that mislabels a perfect score as "medium".
    assert compute_pass_pct(10, 12) == 100
    # A perfect 100% score is "high" against the clamped threshold (not "medium").
    assert compute_score_status(100.0, pass_threshold=compute_pass_pct(10, 12)) == "high"


# --- compute_status ---


async def test_compute_status_returns_passed():
    assert compute_status(has_passed=True, completed_count=5) == "passed"


async def test_compute_status_returns_in_progress():
    assert compute_status(has_passed=False, completed_count=3) == "in-progress"


async def test_compute_status_returns_not_started():
    assert compute_status(has_passed=False, completed_count=0) == "not-started"
    assert compute_status(has_passed=False, completed_count=None) == "not-started"


# --- compute_status_instructional ---


async def test_compute_status_instructional_all_passed():
    assert compute_status_instructional(passed_count=10, in_progress_count=0, total_members=10) == "passed"


async def test_compute_status_instructional_no_members():
    assert compute_status_instructional(passed_count=0, in_progress_count=0, total_members=0) == "passed"


async def test_compute_status_instructional_in_progress():
    assert compute_status_instructional(passed_count=2, in_progress_count=3, total_members=10) == "in-progress"


async def test_compute_status_instructional_not_started():
    assert compute_status_instructional(passed_count=0, in_progress_count=0, total_members=10) == "not-started"


# --- compute_completion_pct ---


async def test_compute_completion_pct_calculates():
    assert compute_completion_pct(passed_count=5, in_progress_count=3, total_members=10) == 80


async def test_compute_completion_pct_zero_total():
    assert compute_completion_pct(passed_count=0, in_progress_count=0, total_members=0) == 0


# --- format_cohort_names ---


async def test_format_cohort_names_none_and_empty():
    assert format_cohort_names(None) is None
    assert format_cohort_names([]) is None


async def test_format_cohort_names_single():
    assert format_cohort_names(["Alpha"]) == "Alpha"


async def test_format_cohort_names_two():
    assert format_cohort_names(["Alpha", "Beta"]) == "Alpha and Beta"


async def test_format_cohort_names_three_or_more():
    result = format_cohort_names(["C", "A", "B"])
    assert result == "A, B, and C"  # sorted and formatted


async def test_format_cohort_names_deduplicates():
    result = format_cohort_names(["A", "A", "B"])
    assert result == "A and B"


# --- compute_show_view ---


async def test_compute_show_view_not_archived():
    assert compute_show_view(is_archived=False) is True


async def test_compute_show_view_archived():
    assert compute_show_view(is_archived=True) is False


async def test_compute_show_view_none():
    assert compute_show_view(is_archived=None) is True


# --- compute_show_continue ---


async def test_compute_show_continue_archived_always_false():
    assert compute_show_continue(
        is_archived=True, infinite_mode=False,
        num_scenarios=5, num_scenarios_completed=0,
        time_limit_seconds=None, elapsed_seconds=None,
        num_incomplete_chats=None,
    ) is False


async def test_compute_show_continue_fixed_mode_not_completed():
    assert compute_show_continue(
        is_archived=False, infinite_mode=False,
        num_scenarios=5, num_scenarios_completed=3,
        time_limit_seconds=None, elapsed_seconds=None,
        num_incomplete_chats=None,
    ) is True


async def test_compute_show_continue_fixed_mode_all_completed():
    assert compute_show_continue(
        is_archived=False, infinite_mode=False,
        num_scenarios=5, num_scenarios_completed=5,
        time_limit_seconds=None, elapsed_seconds=None,
        num_incomplete_chats=None,
    ) is False


async def test_compute_show_continue_infinite_mode_with_pending():
    assert compute_show_continue(
        is_archived=False, infinite_mode=True,
        num_scenarios=None, num_scenarios_completed=None,
        time_limit_seconds=None, elapsed_seconds=None,
        num_incomplete_chats=2,
    ) is True


async def test_compute_show_continue_infinite_mode_time_exceeded():
    assert compute_show_continue(
        is_archived=False, infinite_mode=True,
        num_scenarios=None, num_scenarios_completed=None,
        time_limit_seconds=100, elapsed_seconds=200,
        num_incomplete_chats=2,
    ) is False


# --- compute_bundle_section_show ---


async def test_compute_bundle_section_show_no_flag():
    assert compute_bundle_section_show("names", {}) is True
    assert compute_bundle_section_show("departments", {}) is True


async def test_compute_bundle_section_show_flag_enabled():
    assert compute_bundle_section_show("videos", {"video_enabled": True}) is True


async def test_compute_bundle_section_show_flag_disabled():
    assert compute_bundle_section_show("videos", {"video_enabled": False}) is False
    assert compute_bundle_section_show("videos", {}) is False
