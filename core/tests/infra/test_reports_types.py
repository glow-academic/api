"""Tests for reports type defaults and isolation."""

from app.infra.reports.types import (
    ReportsHistorySection,
    ReportsLeaderboardRow,
    ReportsMetric,
    ReportsMetricHover,
    ReportsSections,
)


def test_reports_metric_defaults_are_initialized():
    metric = ReportsMetric()

    assert metric.current_value is None
    assert metric.has_data is False
    assert metric.data_points == []
    assert metric.hover is None
    assert metric.status == "neutral"


def test_reports_sections_use_independent_default_factories():
    first = ReportsSections()
    second = ReportsSections()

    first.leaderboard.rows.append(
        ReportsLeaderboardRow(
            rank=1,
            profile_id="profile-1",
        )
    )

    assert second.leaderboard.rows == []


def test_reports_hover_and_history_sections_have_stable_defaults():
    hover = ReportsMetricHover()
    history = ReportsHistorySection()

    assert hover.total_hours == 0.0
    assert hover.top == []
    assert history.rows == []
