"""Tests for reports permissions/business logic."""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.infra.reports.permissions import (
    build_reports_sections,
    build_reports_sections_v2,
    compute_history_section,
    compute_history_section_v2,
    compute_leaderboard_section,
    compute_leaderboard_section_v2,
    compute_overview_section,
    compute_overview_section_v2,
    compute_reports_header_metrics,
    compute_reports_header_metrics_v2,
    compute_trends_section,
    compute_trends_section_v2,
)
from app.tools.entries.attempt_chat.types import ChatItem


def _chat(
    *,
    profile_id,
    simulation_id,
    attempt_id=None,
    attempt_date=None,
    scenario_id=None,
    cohort_id=None,
    grade_score=None,
    grade_total_points=100,
    grade_passed=None,
    grade_time_taken=None,
    completed=False,
    attempt_type="general",
    is_archived=False,
    infinite_mode=False,
):
    return ChatItem(
        chat_id=uuid4(),
        attempt_id=attempt_id or uuid4(),
        chat_entry_id=uuid4(),
        group_id=uuid4(),
        attempt_chat_id=uuid4(),
        profile_id=profile_id,
        cohort_id=cohort_id,
        department_id=uuid4(),
        simulation_id=simulation_id,
        scenario_id=scenario_id,
        persona_ids=[uuid4()],
        rubric_id=uuid4(),
        grade_score=grade_score,
        grade_total_points=grade_total_points,
        grade_pass_points=70,
        grade_passed=grade_passed,
        grade_time_taken=grade_time_taken,
        completed=completed,
        attempt_number=1,
        chat_created_at=datetime(2030, 1, 1, tzinfo=UTC),
        attempt_date=attempt_date or date(2030, 1, 1),
        attempt_type=attempt_type,
        is_archived=is_archived,
        infinite_mode=infinite_mode,
        document_ids=[],
    )


def test_compute_reports_header_metrics_v2_aggregates_scores_completion_and_first_attempt():
    profile_a = uuid4()
    profile_b = uuid4()
    simulation_a = uuid4()
    simulation_b = uuid4()

    chats = [
        _chat(
            profile_id=profile_a,
            simulation_id=simulation_a,
            attempt_id=uuid4(),
            attempt_date=date(2030, 1, 1),
            grade_score=80,
            grade_passed=True,
            completed=True,
        ),
        _chat(
            profile_id=profile_a,
            simulation_id=simulation_a,
            attempt_id=uuid4(),
            attempt_date=date(2030, 1, 2),
            grade_score=75,
            grade_passed=False,
            completed=False,
        ),
        _chat(
            profile_id=profile_b,
            simulation_id=simulation_b,
            attempt_id=uuid4(),
            attempt_date=date(2030, 1, 2),
            grade_score=90,
            grade_passed=True,
            completed=True,
        ),
    ]

    result = compute_reports_header_metrics_v2(chats)

    assert result.total_attempts.current_value == 3
    assert result.average_score.current_value == 81.67
    assert result.completion_percentage.current_value == 66.67
    assert result.first_attempt_pass_rate.current_value == 100.0
    assert [point.date for point in result.average_score.data_points] == [
        "2030-01-01",
        "2030-01-02",
    ]


def test_compute_overview_section_v2_groups_by_simulation_and_attempt():
    simulation_a = uuid4()
    simulation_b = uuid4()
    profile_id = uuid4()
    attempt_a = uuid4()
    attempt_b = uuid4()
    attempt_c = uuid4()

    chats = [
        _chat(
            profile_id=profile_id,
            simulation_id=simulation_a,
            attempt_id=attempt_a,
            grade_score=80,
            grade_passed=True,
            completed=True,
        ),
        _chat(
            profile_id=profile_id,
            simulation_id=simulation_a,
            attempt_id=attempt_a,
            grade_score=100,
            grade_passed=True,
            completed=True,
        ),
        _chat(
            profile_id=profile_id,
            simulation_id=simulation_a,
            attempt_id=attempt_b,
            grade_score=60,
            grade_passed=False,
            completed=False,
        ),
        _chat(
            profile_id=profile_id,
            simulation_id=simulation_b,
            attempt_id=attempt_c,
            grade_score=90,
            grade_passed=True,
            completed=True,
        ),
    ]

    result = compute_overview_section_v2(chats)

    assert result.status.has_data is True
    assert result.rows[0].simulation_id == str(simulation_a)
    assert result.rows[0].attempts == 2
    assert result.rows[0].completed_attempts == 1
    assert result.rows[0].passed_attempts == 1
    assert result.rows[0].average_score == 75.0


def test_compute_leaderboard_section_v2_ranks_profiles_and_builds_metrics():
    profile_a = uuid4()
    profile_b = uuid4()
    simulation_id = uuid4()
    scenario_id = uuid4()

    chats = [
        _chat(
            profile_id=profile_a,
            simulation_id=simulation_id,
            scenario_id=scenario_id,
            attempt_id=uuid4(),
            attempt_date=date(2030, 1, 1),
            grade_score=90,
            grade_passed=True,
            grade_time_taken=120,
            completed=True,
        ),
        _chat(
            profile_id=profile_a,
            simulation_id=simulation_id,
            scenario_id=scenario_id,
            attempt_id=uuid4(),
            attempt_date=date(2030, 1, 2),
            grade_score=85,
            grade_passed=True,
            grade_time_taken=60,
            completed=True,
        ),
        _chat(
            profile_id=profile_b,
            simulation_id=simulation_id,
            scenario_id=scenario_id,
            attempt_id=uuid4(),
            attempt_date=date(2030, 1, 1),
            grade_score=70,
            grade_passed=False,
            completed=True,
        ),
        _chat(
            profile_id=profile_b,
            simulation_id=simulation_id,
            scenario_id=scenario_id,
            attempt_id=uuid4(),
            attempt_date=date(2030, 1, 2),
            grade_score=70,
            grade_passed=False,
            completed=True,
        ),
    ]

    result = compute_leaderboard_section_v2(chats)

    assert result.status.has_data is True
    assert result.rows[0].profile_id == str(profile_a)
    assert result.rows[0].rank == 1
    assert result.rows[0].average_score == 87.5
    assert result.rows[0].profile_metrics.time_spent.current_value == 3.0
    assert result.rows[1].profile_metrics.stagnation_rate.current_value == 100.0


def test_compute_trends_section_v2_builds_daily_points():
    profile_id = uuid4()
    simulation_id = uuid4()
    attempt_a = uuid4()
    attempt_b = uuid4()

    chats = [
        _chat(
            profile_id=profile_id,
            simulation_id=simulation_id,
            attempt_id=attempt_a,
            attempt_date=date(2030, 1, 1),
            grade_score=80,
            grade_passed=True,
            completed=True,
        ),
        _chat(
            profile_id=profile_id,
            simulation_id=simulation_id,
            attempt_id=attempt_a,
            attempt_date=date(2030, 1, 1),
            grade_score=100,
            grade_passed=True,
            completed=True,
        ),
        _chat(
            profile_id=profile_id,
            simulation_id=simulation_id,
            attempt_id=attempt_b,
            attempt_date=date(2030, 1, 2),
            grade_score=60,
            grade_passed=False,
            completed=False,
        ),
    ]

    result = compute_trends_section_v2(chats)

    assert [point.date for point in result.chart_data] == ["2030-01-01", "2030-01-02"]
    assert result.chart_data[0].attempts == 1
    assert result.chart_data[0].completion_percentage == 100.0
    assert result.chart_data[1].pass_rate == 0.0


def test_compute_history_section_v2_groups_attempt_rows_and_sorts_desc():
    profile_id = uuid4()
    simulation_id = uuid4()
    cohort_id = uuid4()
    scenario_a = uuid4()
    scenario_b = uuid4()
    newer_attempt = uuid4()
    older_attempt = uuid4()

    chats = [
        _chat(
            profile_id=profile_id,
            simulation_id=simulation_id,
            cohort_id=cohort_id,
            scenario_id=scenario_a,
            attempt_id=older_attempt,
            attempt_date=date(2030, 1, 1),
            grade_score=70,
            grade_passed=False,
            grade_time_taken=30,
            completed=False,
            infinite_mode=True,
        ),
        _chat(
            profile_id=profile_id,
            simulation_id=simulation_id,
            cohort_id=cohort_id,
            scenario_id=scenario_b,
            attempt_id=newer_attempt,
            attempt_date=date(2030, 1, 3),
            grade_score=90,
            grade_passed=True,
            grade_time_taken=45,
            completed=True,
            is_archived=True,
        ),
    ]

    result = compute_history_section_v2(chats)

    assert result.status.has_data is True
    assert result.rows[0].attempt_id == str(newer_attempt)
    assert result.rows[0].has_passed is True
    assert result.rows[0].scenario_ids == [str(scenario_b)]
    assert result.rows[1].attempt_id == str(older_attempt)
    assert result.rows[1].infinite_mode is True


def test_build_reports_sections_v2_returns_empty_sections_for_no_data():
    result = build_reports_sections_v2([])

    assert result.header_metrics.total_attempts.current_value == 0
    assert result.overview.status.has_data is False
    assert result.leaderboard.rows == []
    assert result.trends.chart_data == []
    assert result.history.rows == []


def test_compute_reports_header_metrics_v1_uses_daily_and_profile_rows():
    profile_id = uuid4()
    attempts = [
        SimpleNamespace(score_percent=70.0),
        SimpleNamespace(score_percent=80.0),
    ]
    chat_rows = [SimpleNamespace(completed=True), SimpleNamespace(completed=False)]
    daily_rows = [
        SimpleNamespace(
            date_key=date(2030, 1, 1),
            attempt_count=2,
            completed_count=1,
            passed_count=1,
            avg_score=75.0,
        )
    ]
    profile_rows = [
        SimpleNamespace(
            profile_id=profile_id,
            first_attempt_pass_rate=50.0,
            total_attempts=2,
        )
    ]

    result = compute_reports_header_metrics(
        attempts=attempts,
        chat_rows=chat_rows,
        daily_rows=daily_rows,
        profile_rows=profile_rows,
        total_count=2,
    )

    assert result.total_attempts.current_value == 2
    assert result.average_score.current_value == 75.0
    assert result.completion_percentage.current_value == 50.0
    assert result.first_attempt_pass_rate.current_value == 50.0


def test_v1_sections_build_expected_rows():
    profile_id = uuid4()
    simulation_id = uuid4()
    scenario_id = uuid4()
    cohort_id = uuid4()

    attempts = [
        SimpleNamespace(
            attempt_id=uuid4(),
            profile_id=profile_id,
            simulation_id=simulation_id,
            cohort_id=cohort_id,
            attempt_created_at=datetime(2030, 1, 2, tzinfo=UTC),
            attempt_type="general",
            is_archived=False,
            infinite_mode=False,
            score_percent=90.0,
            has_passed=True,
            num_chats=2,
            num_chats_completed=2,
            total_time_seconds=120,
            scenario_ids=[scenario_id],
        ),
        SimpleNamespace(
            attempt_id=uuid4(),
            profile_id=profile_id,
            simulation_id=simulation_id,
            cohort_id=cohort_id,
            attempt_created_at=datetime(2030, 1, 1, tzinfo=UTC),
            attempt_type="practice",
            is_archived=True,
            infinite_mode=True,
            score_percent=60.0,
            has_passed=False,
            num_chats=1,
            num_chats_completed=0,
            total_time_seconds=30,
            scenario_ids=[scenario_id],
        ),
    ]
    chat_rows = [
        SimpleNamespace(
            profile_id=profile_id,
            grade_percent=90.0,
            grade_created_at=datetime(2030, 1, 1, tzinfo=UTC),
            chat_created_at=datetime(2030, 1, 1, tzinfo=UTC),
            completed=True,
        ),
        SimpleNamespace(
            profile_id=profile_id,
            grade_percent=85.0,
            grade_created_at=datetime(2030, 1, 2, tzinfo=UTC),
            chat_created_at=datetime(2030, 1, 2, tzinfo=UTC),
            completed=True,
        ),
    ]
    daily_rows = [
        SimpleNamespace(
            date_key=date(2030, 1, 1),
            attempt_count=1,
            completed_count=1,
            passed_count=1,
            avg_score=90.0,
        ),
        SimpleNamespace(
            date_key=date(2030, 1, 2),
            attempt_count=1,
            completed_count=0,
            passed_count=0,
            avg_score=60.0,
        ),
    ]
    profile_rows = [
        SimpleNamespace(
            profile_id=profile_id,
            avg_score=87.5,
            completion_pct=50.0,
            first_attempt_pass_rate=100.0,
            highest_score=90.0,
            avg_messages_per_session=4.0,
            avg_persona_response_sec=10.0,
            session_efficiency=43.75,
            total_time_minutes=2.5,
            total_attempts=2,
            simulation_ids=[simulation_id],
            scenario_ids=[scenario_id],
        )
    ]

    overview = compute_overview_section(attempts)
    leaderboard = compute_leaderboard_section(profile_rows, chat_rows)
    trends = compute_trends_section(daily_rows)
    history = compute_history_section(attempts)
    sections = build_reports_sections(
        attempts=attempts,
        chat_rows=chat_rows,
        daily_rows=daily_rows,
        profile_rows=profile_rows,
        total_count=2,
    )

    assert overview.rows[0].attempts == 2
    assert leaderboard.rows[0].average_score == 87.5
    assert leaderboard.rows[0].profile_metrics.stagnation_rate.current_value == 100.0
    assert trends.chart_data[0].date == "2030-01-01"
    assert history.rows[0].attempt_type == "general"
    assert sections.header_metrics.total_attempts.current_value == 2


def test_v1_sections_return_empty_when_no_inputs():
    assert compute_overview_section([]).rows == []
    assert compute_leaderboard_section([], []).rows == []
    assert compute_trends_section([]).chart_data == []
    assert compute_history_section([]).rows == []
