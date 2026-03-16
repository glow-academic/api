"""Reports calculation/business logic for get.py."""

from collections import defaultdict
from datetime import date, datetime
from typing import Any

from app.infra.reports.types import (
    ReportsDataPoint,
    ReportsHeaderMetrics,
    ReportsHistoryRow,
    ReportsHistorySection,
    ReportsLeaderboardRow,
    ReportsLeaderboardSection,
    ReportsMetric,
    ReportsMetricHover,
    ReportsOverviewRow,
    ReportsOverviewSection,
    ReportsProfileMetrics,
    ReportsSections,
    ReportsSectionStatus,
    ReportsTrendPoint,
    ReportsTrendsSection,
)
from app.tools.entries.attempt_chat.types import ChatItem

# Type aliases for deprecated v1 types (modules deleted in DELETE OLD VIEWS)
AttemptFactsItem = Any
ChatFactsItem = Any
DailyMetricsItem = Any
ProfileMetricsItem = Any


def _metric(value: float | int | None) -> ReportsMetric:
    return ReportsMetric(
        current_value=value,
        has_data=value is not None,
        method=None,
        data_points=[],
        hover=None,
        status="neutral",
    )


def _section(has_data: bool, note: str | None = None) -> ReportsSectionStatus:
    return ReportsSectionStatus(
        has_data=has_data,
        status="neutral" if has_data else "empty",
        note=note,
    )


def _round2(value: float | int | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _date_str(value: date | datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _status_standard(value: float | int | None, thresholds: dict[str, int]) -> str:
    if value is None or float(value) == 0:
        return "neutral"
    rounded = round(float(value))
    if rounded >= thresholds["success"]:
        return "success"
    if rounded >= thresholds["warning"]:
        return "warning"
    return "danger"


def _status_inverse(value: float | int | None, thresholds: dict[str, int]) -> str:
    if value is None or float(value) == 0:
        return "neutral"
    rounded = round(float(value))
    if rounded > thresholds["danger"]:
        return "danger"
    if rounded > thresholds["warning"]:
        return "warning"
    return "success"


def _metric_envelope(
    *,
    value: float | int | None,
    method: str,
    status: str,
    data_points: list[ReportsDataPoint] | None = None,
    hover: ReportsMetricHover | None = None,
) -> ReportsMetric:
    return ReportsMetric(
        current_value=_round2(value),
        has_data=value is not None and float(value) > 0,
        method=method,
        data_points=data_points or [],
        hover=hover,
        status=status,
    )


def _compute_stagnation_stats(
    chat_rows: list[ChatFactsItem],
) -> dict[str, tuple[float, int, int, list[ReportsDataPoint]]]:
    """Compute legacy-style stagnation rate per profile from ordered grade stream.

    Legacy rule mirrored from SQL:
    - Compare each grade to previous grade in chronological order
    - Mark stagnated when current <= previous + 0.1
    - stagnation_rate = 100 * avg(stagnated_flags)
    """
    profile_grades: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
    for row in chat_rows:
        if row.profile_id is None or row.grade_percent is None:
            continue
        ts = row.grade_created_at or row.chat_created_at
        profile_grades[str(row.profile_id)].append((ts, float(row.grade_percent)))

    out: dict[str, tuple[float, int, int, list[ReportsDataPoint]]] = {}
    for profile_id, entries in profile_grades.items():
        ordered = sorted(entries, key=lambda item: item[0])
        if len(ordered) < 2:
            out[profile_id] = (0.0, 0, 0, [])
            continue

        tracked = 0
        stagnant = 0
        points: list[ReportsDataPoint] = []
        prev_score: float | None = None
        for ts, score in ordered:
            points.append(
                ReportsDataPoint(
                    profile_id=profile_id,
                    date=_date_str(ts.date()),
                    value=_round2(score),
                )
            )
            if prev_score is None:
                prev_score = score
                continue
            tracked += 1
            if score <= prev_score + 0.1:
                stagnant += 1
            prev_score = score

        rate = (stagnant / tracked * 100.0) if tracked > 0 else 0.0
        out[profile_id] = (_round2(rate) or 0.0, tracked, stagnant, points)

    return out


def compute_reports_header_metrics(
    attempts: list[AttemptFactsItem],
    chat_rows: list[ChatFactsItem],
    daily_rows: list[DailyMetricsItem],
    profile_rows: list[ProfileMetricsItem],
    total_count: int = 0,
    thresholds: dict[str, int] | None = None,
) -> ReportsHeaderMetrics:
    """Compute top-level report summary metrics from MV slices."""
    thresholds = thresholds or {"success": 85, "warning": 80, "danger": 70}
    total_attempts = total_count if total_count > 0 else len(attempts)

    # Weighted by attempt_count from daily slice where possible.
    weighted_score_sum = 0.0
    weighted_score_n = 0
    for row in daily_rows:
        attempts_n = row.attempt_count or 0
        if attempts_n <= 0:
            continue
        if row.avg_score is not None:
            weighted_score_sum += float(row.avg_score) * attempts_n
            weighted_score_n += attempts_n

    average_score = (
        round(weighted_score_sum / weighted_score_n, 2)
        if weighted_score_n > 0
        else None
    )

    # Fallback to attempt rows if daily metrics are empty.
    if average_score is None:
        attempt_scores = [
            float(attempt.score_percent)
            for attempt in attempts
            if attempt.score_percent is not None
        ]
        if attempt_scores:
            average_score = round(sum(attempt_scores) / len(attempt_scores), 2)

    completed_count = sum(1 for row in chat_rows if row.completed)
    completion_pct = (
        round((completed_count / total_attempts) * 100, 2)
        if total_attempts > 0
        else None
    )

    # Use weighted profile-metrics aggregate (matches profile-level rollups better).
    weighted_first_attempt_sum = 0.0
    weighted_first_attempt_n = 0
    for row in profile_rows:
        if row.first_attempt_pass_rate is None:
            continue
        attempts_n = row.total_attempts or 0
        if attempts_n <= 0:
            continue
        weighted_first_attempt_sum += float(row.first_attempt_pass_rate) * attempts_n
        weighted_first_attempt_n += attempts_n
    first_attempt_pass_rate = (
        round(weighted_first_attempt_sum / weighted_first_attempt_n, 2)
        if weighted_first_attempt_n > 0
        else None
    )

    avg_score_points = [
        ReportsDataPoint(date=_date_str(row.date_key), value=_round2(row.avg_score))
        for row in sorted(daily_rows, key=lambda r: r.date_key)
        if row.avg_score is not None
    ]
    completion_points = [
        ReportsDataPoint(
            date=_date_str(row.date_key),
            value=_round2(
                ((row.completed_count or 0) / (row.attempt_count or 1) * 100)
                if (row.attempt_count or 0) > 0
                else None
            ),
        )
        for row in sorted(daily_rows, key=lambda r: r.date_key)
        if (row.attempt_count or 0) > 0
    ]
    first_attempt_points = [
        ReportsDataPoint(
            profile_id=str(row.profile_id),
            value=_round2(row.first_attempt_pass_rate),
        )
        for row in profile_rows
        if row.first_attempt_pass_rate is not None
    ]

    return ReportsHeaderMetrics(
        total_attempts=_metric_envelope(
            value=total_attempts,
            method="countDistinct",
            status=_status_standard(total_attempts, thresholds),
            hover=ReportsMetricHover(attempts=total_attempts),
        ),
        average_score=_metric_envelope(
            value=average_score,
            method="avg",
            status=_status_standard(average_score, thresholds),
            data_points=avg_score_points,
            hover=ReportsMetricHover(
                mean=round(average_score) if average_score is not None else 0,
                median=round(average_score) if average_score is not None else 0,
                mode=round(average_score) if average_score is not None else 0,
                avg_score_percent=round(average_score)
                if average_score is not None
                else 0,
            ),
        ),
        completion_percentage=_metric_envelope(
            value=completion_pct,
            method="rate",
            status=_status_standard(completion_pct, thresholds),
            data_points=completion_points,
            hover=ReportsMetricHover(
                completed=completed_count,
                total=total_attempts,
                percent=round(completion_pct) if completion_pct is not None else 0,
            ),
        ),
        first_attempt_pass_rate=_metric_envelope(
            value=first_attempt_pass_rate,
            method="rate",
            status=_status_standard(first_attempt_pass_rate, thresholds),
            data_points=first_attempt_points,
            hover=ReportsMetricHover(
                percent=round(first_attempt_pass_rate)
                if first_attempt_pass_rate is not None
                else 0,
            ),
        ),
    )


def _build_profile_metrics(
    row: ProfileMetricsItem,
    thresholds: dict[str, int],
    stagnation_stats: dict[str, tuple[float, int, int, list[ReportsDataPoint]]],
) -> ReportsProfileMetrics:
    avg_score = _round2(row.avg_score)
    completion_pct = _round2(row.completion_pct)
    first_attempt = _round2(row.first_attempt_pass_rate)
    highest_score = _round2(row.highest_score)
    avg_messages = _round2(row.avg_messages_per_session)
    persona_response = _round2(row.avg_persona_response_sec)
    session_efficiency = _round2(row.session_efficiency)
    profile_key = str(row.profile_id)
    stagnation_rate, tracked, stagnant, stagnation_points = stagnation_stats.get(
        profile_key,
        (0.0, 0, 0, []),
    )
    total_minutes = _round2(row.total_time_minutes)
    total_attempts = row.total_attempts or 0

    return ReportsProfileMetrics(
        average_score=_metric_envelope(
            value=avg_score,
            method="avg",
            status=_status_standard(avg_score, thresholds),
            hover=ReportsMetricHover(
                mean=round(avg_score) if avg_score is not None else 0,
                median=round(avg_score) if avg_score is not None else 0,
                mode=round(avg_score) if avg_score is not None else 0,
                avg_score_percent=round(avg_score) if avg_score is not None else 0,
            ),
        ),
        completion_percentage=_metric_envelope(
            value=completion_pct,
            method="rate",
            status=_status_standard(completion_pct, thresholds),
            hover=ReportsMetricHover(
                percent=round(completion_pct) if completion_pct is not None else 0,
            ),
        ),
        first_attempt_pass_rate=_metric_envelope(
            value=first_attempt,
            method="rate",
            status=_status_standard(first_attempt, thresholds),
            hover=ReportsMetricHover(
                percent=round(first_attempt) if first_attempt is not None else 0,
            ),
        ),
        highest_score=_metric_envelope(
            value=highest_score,
            method="max",
            status=_status_standard(highest_score, thresholds),
            hover=ReportsMetricHover(
                top=[round(highest_score)] if highest_score is not None else [],
            ),
        ),
        messages_per_session=_metric_envelope(
            value=avg_messages,
            method="avg",
            status=_status_standard(avg_messages, thresholds),
            hover=ReportsMetricHover(
                mean=round(avg_messages) if avg_messages is not None else 0,
                median=round(avg_messages) if avg_messages is not None else 0,
                count=total_attempts,
            ),
        ),
        persona_response_times=_metric_envelope(
            value=persona_response,
            method="avg",
            status=_status_inverse(persona_response, thresholds),
            hover=ReportsMetricHover(
                mean_seconds=round(persona_response)
                if persona_response is not None
                else 0,
                median_seconds=round(persona_response)
                if persona_response is not None
                else 0,
            ),
        ),
        session_efficiency=_metric_envelope(
            value=session_efficiency,
            method="avg",
            status=_status_standard(session_efficiency, thresholds),
            hover=ReportsMetricHover(
                efficiency=round(session_efficiency)
                if session_efficiency is not None
                else 0,
            ),
        ),
        stagnation_rate=_metric_envelope(
            value=stagnation_rate,
            method="rate",
            status=_status_inverse(stagnation_rate, thresholds),
            data_points=stagnation_points,
            hover=ReportsMetricHover(
                tracked=tracked,
                stagnant=stagnant,
                rate_percent=round(stagnation_rate),
            ),
        ),
        time_spent=_metric_envelope(
            value=total_minutes,
            method="sum",
            status=_status_standard(total_minutes, thresholds),
            hover=ReportsMetricHover(
                total_minutes=round(total_minutes) if total_minutes is not None else 0,
                total_hours=round((total_minutes or 0) / 60.0, 1),
            ),
        ),
        total_attempts=_metric_envelope(
            value=total_attempts,
            method="countDistinct",
            status=_status_standard(total_attempts, thresholds),
            hover=ReportsMetricHover(attempts=total_attempts),
        ),
    )


def compute_overview_section(
    attempts: list[AttemptFactsItem],
) -> ReportsOverviewSection:
    """Compute simulation-level overview aggregates."""
    grouped: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "attempts": 0.0,
            "completed": 0.0,
            "passed": 0.0,
            "score_sum": 0.0,
            "score_n": 0.0,
        }
    )

    for attempt in attempts:
        if attempt.simulation_id is None:
            continue
        key = str(attempt.simulation_id)
        bucket = grouped[key]
        bucket["attempts"] += 1
        if (attempt.num_chats or 0) > 0 and (attempt.num_chats_completed or 0) >= (
            attempt.num_chats or 0
        ):
            bucket["completed"] += 1
        if attempt.has_passed:
            bucket["passed"] += 1
        if attempt.score_percent is not None:
            bucket["score_sum"] += float(attempt.score_percent)
            bucket["score_n"] += 1

    rows: list[ReportsOverviewRow] = []
    for simulation_id, bucket in grouped.items():
        attempts_n = int(bucket["attempts"])
        completed_n = int(bucket["completed"])
        passed_n = int(bucket["passed"])
        avg_score = (
            bucket["score_sum"] / bucket["score_n"] if bucket["score_n"] > 0 else None
        )
        completion_pct = (completed_n / attempts_n) * 100 if attempts_n > 0 else None
        pass_rate = (passed_n / attempts_n) * 100 if attempts_n > 0 else None
        rows.append(
            ReportsOverviewRow(
                simulation_id=simulation_id,
                attempts=attempts_n,
                completed_attempts=completed_n,
                passed_attempts=passed_n,
                average_score=_round2(avg_score),
                completion_percentage=_round2(completion_pct),
                pass_rate=_round2(pass_rate),
            )
        )

    rows.sort(
        key=lambda row: (
            row.attempts,
            row.average_score if row.average_score is not None else -1.0,
        ),
        reverse=True,
    )
    return ReportsOverviewSection(
        status=_section(bool(rows), "Derived from mv_profile_facts"),
        rows=rows,
    )


def compute_leaderboard_section(
    profile_rows: list[ProfileMetricsItem],
    chat_rows: list[ChatFactsItem],
    thresholds: dict[str, int] | None = None,
) -> ReportsLeaderboardSection:
    """Compute leaderboard rows from profile metrics slice."""
    thresholds = thresholds or {"success": 85, "warning": 80, "danger": 70}
    stagnation_stats = _compute_stagnation_stats(chat_rows)
    sorted_rows = sorted(
        profile_rows,
        key=lambda row: (
            float(row.avg_score) if row.avg_score is not None else -1.0,
            row.total_attempts,
        ),
        reverse=True,
    )

    rows: list[ReportsLeaderboardRow] = []
    for index, row in enumerate(sorted_rows):
        rows.append(
            ReportsLeaderboardRow(
                rank=index + 1,
                profile_id=str(row.profile_id) if row.profile_id else None,
                total_attempts=row.total_attempts or 0,
                average_score=_round2(row.avg_score),
                highest_score=_round2(row.highest_score),
                completion_percentage=_round2(row.completion_pct),
                first_attempt_pass_rate=_round2(row.first_attempt_pass_rate),
                profile_metrics=_build_profile_metrics(
                    row=row,
                    thresholds=thresholds,
                    stagnation_stats=stagnation_stats,
                ),
                simulation_ids=[str(sid) for sid in row.simulation_ids or []],
                scenario_ids=[str(sid) for sid in row.scenario_ids or []],
            )
        )

    return ReportsLeaderboardSection(
        status=_section(bool(rows), "Derived from mv_profile_metrics"),
        rows=rows,
    )


def compute_trends_section(
    daily_rows: list[DailyMetricsItem],
) -> ReportsTrendsSection:
    """Compute daily trend points from daily metrics slice."""
    grouped: dict[date, dict[str, float]] = defaultdict(
        lambda: {
            "attempts": 0.0,
            "completed": 0.0,
            "passed": 0.0,
            "score_sum": 0.0,
            "score_n": 0.0,
        }
    )

    for row in daily_rows:
        bucket = grouped[row.date_key]
        attempts_n = float(row.attempt_count or 0)
        bucket["attempts"] += attempts_n
        bucket["completed"] += float(row.completed_count or 0)
        bucket["passed"] += float(row.passed_count or 0)
        if row.avg_score is not None and attempts_n > 0:
            bucket["score_sum"] += float(row.avg_score) * attempts_n
            bucket["score_n"] += attempts_n

    points: list[ReportsTrendPoint] = []
    for day in sorted(grouped.keys()):
        bucket = grouped[day]
        attempts_n = int(bucket["attempts"])
        completed_n = int(bucket["completed"])
        passed_n = int(bucket["passed"])
        avg_score = (
            bucket["score_sum"] / bucket["score_n"] if bucket["score_n"] > 0 else None
        )
        completion_pct = (completed_n / attempts_n) * 100 if attempts_n > 0 else None
        pass_rate = (passed_n / attempts_n) * 100 if attempts_n > 0 else None
        points.append(
            ReportsTrendPoint(
                date=_date_str(day),
                attempts=attempts_n,
                completed_attempts=completed_n,
                passed_attempts=passed_n,
                average_score=_round2(avg_score),
                completion_percentage=_round2(completion_pct),
                pass_rate=_round2(pass_rate),
            )
        )

    return ReportsTrendsSection(
        status=_section(bool(points), "Derived from mv_daily_metrics"),
        chart_data=points,
    )


def compute_history_section(
    attempts: list[AttemptFactsItem],
) -> ReportsHistorySection:
    """Compute history rows from attempt facts slice."""
    rows: list[ReportsHistoryRow] = []
    for attempt in sorted(
        attempts,
        key=lambda row: (
            row.attempt_created_at
            if row.attempt_created_at is not None
            else datetime.min
        ),
        reverse=True,
    ):
        rows.append(
            ReportsHistoryRow(
                attempt_id=str(attempt.attempt_id),
                profile_id=str(attempt.profile_id) if attempt.profile_id else None,
                simulation_id=str(attempt.simulation_id)
                if attempt.simulation_id
                else None,
                cohort_id=str(attempt.cohort_id) if attempt.cohort_id else None,
                attempt_created_at=attempt.attempt_created_at,
                attempt_type=attempt.attempt_type,
                is_archived=attempt.is_archived,
                infinite_mode=attempt.infinite_mode,
                score_percent=_round2(attempt.score_percent),
                has_passed=attempt.has_passed,
                num_chats=attempt.num_chats or 0,
                num_chats_completed=attempt.num_chats_completed or 0,
                total_time_seconds=attempt.total_time_seconds or 0,
                scenario_ids=[str(sid) for sid in attempt.scenario_ids or []],
            )
        )

    return ReportsHistorySection(
        status=_section(bool(rows), "Uses mv_profile_facts timeline"),
        rows=rows,
    )


def build_reports_sections(
    attempts: list[AttemptFactsItem],
    chat_rows: list[ChatFactsItem],
    daily_rows: list[DailyMetricsItem],
    profile_rows: list[ProfileMetricsItem],
    total_count: int = 0,
    thresholds: dict[str, int] | None = None,
) -> ReportsSections:
    """Build section-computation skeleton for reports artifact.

    Notes:
    - overview: attempt-level base facts
    - leaderboard: profile-level ranks/summaries
    - trends: daily time-series + chat-level detail context
    - history: attempt/chat event coverage
    """
    header_metrics = compute_reports_header_metrics(
        attempts=attempts,
        chat_rows=chat_rows,
        daily_rows=daily_rows,
        profile_rows=profile_rows,
        total_count=total_count,
        thresholds=thresholds,
    )

    return ReportsSections(
        header_metrics=header_metrics,
        overview=compute_overview_section(attempts=attempts),
        leaderboard=compute_leaderboard_section(
            profile_rows=profile_rows,
            chat_rows=chat_rows,
            thresholds=thresholds,
        ),
        trends=compute_trends_section(daily_rows=daily_rows),
        history=compute_history_section(attempts=attempts),
    )


# ---------------------------------------------------------------------------
# v2 functions: all computation from ChatItem (mv_profile_facts)
# ---------------------------------------------------------------------------


def _compute_stagnation_stats_v2(
    profile_facts_items: list[ChatItem],
) -> dict[str, tuple[float, int, int, list[ReportsDataPoint]]]:
    """Compute stagnation rate per profile from chronological grade stream.

    Same logic as _compute_stagnation_stats but operates on ChatItem rows.
    """
    profile_grades: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for item in profile_facts_items:
        if item.grade_percent is None or item.attempt_date is None:
            continue
        profile_grades[str(item.profile_id)].append(
            (item.attempt_date, float(item.grade_percent))
        )

    out: dict[str, tuple[float, int, int, list[ReportsDataPoint]]] = {}
    for profile_id, entries in profile_grades.items():
        ordered = sorted(entries, key=lambda e: e[0])
        if len(ordered) < 2:
            out[profile_id] = (0.0, 0, 0, [])
            continue

        tracked = 0
        stagnant = 0
        points: list[ReportsDataPoint] = []
        prev_score: float | None = None
        for d, score in ordered:
            points.append(
                ReportsDataPoint(
                    profile_id=profile_id,
                    date=_date_str(d),
                    value=_round2(score),
                )
            )
            if prev_score is None:
                prev_score = score
                continue
            tracked += 1
            if score <= prev_score + 0.1:
                stagnant += 1
            prev_score = score

        rate = (stagnant / tracked * 100.0) if tracked > 0 else 0.0
        out[profile_id] = (_round2(rate) or 0.0, tracked, stagnant, points)

    return out


def compute_reports_header_metrics_v2(
    profile_facts_items: list[ChatItem],
    total_count: int = 0,
    thresholds: dict[str, int] | None = None,
) -> ReportsHeaderMetrics:
    """Compute top-level report summary metrics from ChatItem rows."""
    thresholds = thresholds or {"success": 85, "warning": 80, "danger": 70}

    # total_attempts: count distinct attempt_ids (or use total_count)
    distinct_attempt_ids = {item.attempt_id for item in profile_facts_items}
    total_attempts = total_count if total_count > 0 else len(distinct_attempt_ids)

    # average_score: weighted avg of grade_percent grouped by date
    date_scores: dict[date, list[float]] = defaultdict(list)
    for item in profile_facts_items:
        if item.grade_percent is not None and item.attempt_date is not None:
            date_scores[item.attempt_date].append(float(item.grade_percent))

    weighted_score_sum = 0.0
    weighted_score_n = 0
    avg_score_points: list[ReportsDataPoint] = []
    for d in sorted(date_scores.keys()):
        scores = date_scores[d]
        day_avg = sum(scores) / len(scores)
        day_count = len(scores)
        weighted_score_sum += day_avg * day_count
        weighted_score_n += day_count
        avg_score_points.append(
            ReportsDataPoint(date=_date_str(d), value=_round2(day_avg))
        )

    average_score = (
        round(weighted_score_sum / weighted_score_n, 2)
        if weighted_score_n > 0
        else None
    )

    # completion_percentage: count(completed=True) / total_chats * 100
    total_chats = len(profile_facts_items)
    completed_count = sum(1 for item in profile_facts_items if item.completed)
    completion_pct = (
        round((completed_count / total_chats) * 100, 2) if total_chats > 0 else None
    )

    # completion trend data_points: per-date completion rate
    date_completion: dict[date, dict[str, int]] = defaultdict(
        lambda: {"completed": 0, "total": 0}
    )
    for item in profile_facts_items:
        if item.attempt_date is not None:
            date_completion[item.attempt_date]["total"] += 1
            if item.completed:
                date_completion[item.attempt_date]["completed"] += 1
    completion_points: list[ReportsDataPoint] = []
    for d in sorted(date_completion.keys()):
        bucket = date_completion[d]
        if bucket["total"] > 0:
            completion_points.append(
                ReportsDataPoint(
                    date=_date_str(d),
                    value=_round2(bucket["completed"] / bucket["total"] * 100),
                )
            )

    # first_attempt_pass_rate: For each profile, find first completed chat, check if passed
    # Group by profile, find earliest completed chat per profile, check passed
    profile_first_completed: dict[str, tuple[date, bool]] = {}
    # Pre-compute per-profile attempt counts
    profile_attempt_counts_map: dict[str, int] = defaultdict(int)
    profile_attempt_ids: dict[str, set] = defaultdict(set)
    for item in profile_facts_items:
        pid = str(item.profile_id)
        profile_attempt_ids[pid].add(item.attempt_id)
    for pid, aids in profile_attempt_ids.items():
        profile_attempt_counts_map[pid] = len(aids)

    # Find first completed chat per profile (by attempt_date)
    for item in profile_facts_items:
        if not item.completed or item.attempt_date is None:
            continue
        pid = str(item.profile_id)
        passed = bool(item.grade_passed)
        if (
            pid not in profile_first_completed
            or item.attempt_date < profile_first_completed[pid][0]
        ):
            profile_first_completed[pid] = (item.attempt_date, passed)

    # Weighted first_attempt_pass_rate by profile attempt count
    weighted_first_attempt_sum = 0.0
    weighted_first_attempt_n = 0
    first_attempt_points: list[ReportsDataPoint] = []
    for pid, (_, passed) in profile_first_completed.items():
        attempt_n = profile_attempt_counts_map.get(pid, 0)
        if attempt_n <= 0:
            continue
        pass_rate_val = 100.0 if passed else 0.0
        weighted_first_attempt_sum += pass_rate_val * attempt_n
        weighted_first_attempt_n += attempt_n
        first_attempt_points.append(
            ReportsDataPoint(
                profile_id=pid,
                value=_round2(pass_rate_val),
            )
        )

    first_attempt_pass_rate = (
        round(weighted_first_attempt_sum / weighted_first_attempt_n, 2)
        if weighted_first_attempt_n > 0
        else None
    )

    return ReportsHeaderMetrics(
        total_attempts=_metric_envelope(
            value=total_attempts,
            method="countDistinct",
            status=_status_standard(total_attempts, thresholds),
            hover=ReportsMetricHover(attempts=total_attempts),
        ),
        average_score=_metric_envelope(
            value=average_score,
            method="avg",
            status=_status_standard(average_score, thresholds),
            data_points=avg_score_points,
            hover=ReportsMetricHover(
                mean=round(average_score) if average_score is not None else 0,
                median=round(average_score) if average_score is not None else 0,
                mode=round(average_score) if average_score is not None else 0,
                avg_score_percent=round(average_score)
                if average_score is not None
                else 0,
            ),
        ),
        completion_percentage=_metric_envelope(
            value=completion_pct,
            method="rate",
            status=_status_standard(completion_pct, thresholds),
            data_points=completion_points,
            hover=ReportsMetricHover(
                completed=completed_count,
                total=total_chats,
                percent=round(completion_pct) if completion_pct is not None else 0,
            ),
        ),
        first_attempt_pass_rate=_metric_envelope(
            value=first_attempt_pass_rate,
            method="rate",
            status=_status_standard(first_attempt_pass_rate, thresholds),
            data_points=first_attempt_points,
            hover=ReportsMetricHover(
                percent=round(first_attempt_pass_rate)
                if first_attempt_pass_rate is not None
                else 0,
            ),
        ),
    )


def compute_overview_section_v2(
    profile_facts_items: list[ChatItem],
) -> ReportsOverviewSection:
    """Compute simulation-level overview aggregates from ChatItem rows."""
    # Group by simulation_id, then by attempt_id within each simulation
    sim_attempts: dict[str, dict[str, list[ChatItem]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for item in profile_facts_items:
        sim_key = str(item.simulation_id)
        att_key = str(item.attempt_id)
        sim_attempts[sim_key][att_key].append(item)

    rows: list[ReportsOverviewRow] = []
    for simulation_id, attempts_map in sim_attempts.items():
        attempts_n = len(attempts_map)
        completed_n = 0
        passed_n = 0
        score_sum = 0.0
        score_count = 0

        for _attempt_id, chats in attempts_map.items():
            # Completed attempt: all chats in attempt are completed
            all_completed = all(c.completed for c in chats)
            if all_completed:
                completed_n += 1
            # Passed attempt: any chat passed
            any_passed = any(
                c.grade_passed for c in chats if c.grade_passed is not None
            )
            if any_passed:
                passed_n += 1
            # Average score_percent per attempt
            chat_scores = [
                float(c.grade_percent) for c in chats if c.grade_percent is not None
            ]
            if chat_scores:
                attempt_avg = sum(chat_scores) / len(chat_scores)
                score_sum += attempt_avg
                score_count += 1

        avg_score = score_sum / score_count if score_count > 0 else None
        completion_pct = (completed_n / attempts_n) * 100 if attempts_n > 0 else None
        pass_rate = (passed_n / attempts_n) * 100 if attempts_n > 0 else None

        rows.append(
            ReportsOverviewRow(
                simulation_id=simulation_id,
                attempts=attempts_n,
                completed_attempts=completed_n,
                passed_attempts=passed_n,
                average_score=_round2(avg_score),
                completion_percentage=_round2(completion_pct),
                pass_rate=_round2(pass_rate),
            )
        )

    rows.sort(
        key=lambda row: (
            row.attempts,
            row.average_score if row.average_score is not None else -1.0,
        ),
        reverse=True,
    )
    return ReportsOverviewSection(
        status=_section(bool(rows), "Derived from mv_profile_facts"),
        rows=rows,
    )


def _build_profile_metrics_v2(
    profile_id: str,
    items: list[ChatItem],
    thresholds: dict[str, int],
    stagnation_stats: dict[str, tuple[float, int, int, list[ReportsDataPoint]]],
) -> ReportsProfileMetrics:
    """Build ReportsProfileMetrics from ChatItem rows for a single profile."""
    # Distinct attempts
    attempt_ids = {item.attempt_id for item in items}
    total_attempts = len(attempt_ids)

    # avg_score
    scores = [
        float(item.grade_percent) for item in items if item.grade_percent is not None
    ]
    avg_score = _round2(sum(scores) / len(scores)) if scores else None

    # highest_score
    highest_score = _round2(max(scores)) if scores else None

    # completion_pct
    total_chats = len(items)
    completed_chats = sum(1 for item in items if item.completed)
    completion_pct = _round2(
        (completed_chats / total_chats * 100) if total_chats > 0 else None
    )

    # first_attempt_pass_rate: find first completed chat, check if passed
    completed_items = [
        item for item in items if item.completed and item.attempt_date is not None
    ]
    first_attempt = None
    if completed_items:
        first_completed = min(completed_items, key=lambda i: i.attempt_date)  # type: ignore[arg-type]
        first_attempt = 100.0 if first_completed.grade_passed else 0.0
    first_attempt_val = _round2(first_attempt)

    # avg_messages — not available on ChatItem (needs service call)
    msg_counts: list[int] = []
    avg_messages = _round2(sum(msg_counts) / len(msg_counts)) if msg_counts else None

    # persona_response (avg_response_sec) — not available on ChatItem (needs service call)
    response_secs: list[float] = []
    persona_response = (
        _round2(sum(response_secs) / len(response_secs)) if response_secs else None
    )

    # session_efficiency: completion_pct * avg_score / 100 (approximation)
    session_efficiency = None
    if completion_pct is not None and avg_score is not None:
        session_efficiency = _round2(completion_pct * avg_score / 100)

    # stagnation
    stagnation_rate, tracked, stagnant, stagnation_points = stagnation_stats.get(
        profile_id, (0.0, 0, 0, [])
    )

    # time_spent: total_time_minutes from sum of grade_time_taken
    total_seconds = sum(
        item.grade_time_taken for item in items if item.grade_time_taken is not None
    )
    total_minutes = _round2(total_seconds / 60.0) if total_seconds > 0 else None

    return ReportsProfileMetrics(
        average_score=_metric_envelope(
            value=avg_score,
            method="avg",
            status=_status_standard(avg_score, thresholds),
            hover=ReportsMetricHover(
                mean=round(avg_score) if avg_score is not None else 0,
                median=round(avg_score) if avg_score is not None else 0,
                mode=round(avg_score) if avg_score is not None else 0,
                avg_score_percent=round(avg_score) if avg_score is not None else 0,
            ),
        ),
        completion_percentage=_metric_envelope(
            value=completion_pct,
            method="rate",
            status=_status_standard(completion_pct, thresholds),
            hover=ReportsMetricHover(
                percent=round(completion_pct) if completion_pct is not None else 0,
            ),
        ),
        first_attempt_pass_rate=_metric_envelope(
            value=first_attempt_val,
            method="rate",
            status=_status_standard(first_attempt_val, thresholds),
            hover=ReportsMetricHover(
                percent=round(first_attempt_val)
                if first_attempt_val is not None
                else 0,
            ),
        ),
        highest_score=_metric_envelope(
            value=highest_score,
            method="max",
            status=_status_standard(highest_score, thresholds),
            hover=ReportsMetricHover(
                top=[round(highest_score)] if highest_score is not None else [],
            ),
        ),
        messages_per_session=_metric_envelope(
            value=avg_messages,
            method="avg",
            status=_status_standard(avg_messages, thresholds),
            hover=ReportsMetricHover(
                mean=round(avg_messages) if avg_messages is not None else 0,
                median=round(avg_messages) if avg_messages is not None else 0,
                count=total_attempts,
            ),
        ),
        persona_response_times=_metric_envelope(
            value=persona_response,
            method="avg",
            status=_status_inverse(persona_response, thresholds),
            hover=ReportsMetricHover(
                mean_seconds=round(persona_response)
                if persona_response is not None
                else 0,
                median_seconds=round(persona_response)
                if persona_response is not None
                else 0,
            ),
        ),
        session_efficiency=_metric_envelope(
            value=session_efficiency,
            method="avg",
            status=_status_standard(session_efficiency, thresholds),
            hover=ReportsMetricHover(
                efficiency=round(session_efficiency)
                if session_efficiency is not None
                else 0,
            ),
        ),
        stagnation_rate=_metric_envelope(
            value=stagnation_rate,
            method="rate",
            status=_status_inverse(stagnation_rate, thresholds),
            data_points=stagnation_points,
            hover=ReportsMetricHover(
                tracked=tracked,
                stagnant=stagnant,
                rate_percent=round(stagnation_rate),
            ),
        ),
        time_spent=_metric_envelope(
            value=total_minutes,
            method="sum",
            status=_status_standard(total_minutes, thresholds),
            hover=ReportsMetricHover(
                total_minutes=round(total_minutes) if total_minutes is not None else 0,
                total_hours=round((total_minutes or 0) / 60.0, 1),
            ),
        ),
        total_attempts=_metric_envelope(
            value=total_attempts,
            method="countDistinct",
            status=_status_standard(total_attempts, thresholds),
            hover=ReportsMetricHover(attempts=total_attempts),
        ),
    )


def compute_leaderboard_section_v2(
    profile_facts_items: list[ChatItem],
    thresholds: dict[str, int] | None = None,
) -> ReportsLeaderboardSection:
    """Compute leaderboard rows from ChatItem rows."""
    thresholds = thresholds or {"success": 85, "warning": 80, "danger": 70}
    stagnation_stats = _compute_stagnation_stats_v2(profile_facts_items)

    # Group items by profile_id
    profile_items: dict[str, list[ChatItem]] = defaultdict(list)
    for item in profile_facts_items:
        profile_items[str(item.profile_id)].append(item)

    # Build per-profile summary for sorting
    profile_summaries: list[tuple[str, float, int, list[ChatItem]]] = []
    for pid, items in profile_items.items():
        scores = [float(i.grade_percent) for i in items if i.grade_percent is not None]
        avg = sum(scores) / len(scores) if scores else -1.0
        attempt_count = len({i.attempt_id for i in items})
        profile_summaries.append((pid, avg, attempt_count, items))

    # Sort by avg_score desc, then total_attempts desc
    profile_summaries.sort(key=lambda x: (x[1], x[2]), reverse=True)

    rows: list[ReportsLeaderboardRow] = []
    for index, (pid, _avg, attempt_count, items) in enumerate(profile_summaries):
        scores = [float(i.grade_percent) for i in items if i.grade_percent is not None]
        avg_score = _round2(sum(scores) / len(scores)) if scores else None
        highest_score = _round2(max(scores)) if scores else None
        total_chats = len(items)
        completed_chats = sum(1 for i in items if i.completed)
        completion_pct = _round2(
            (completed_chats / total_chats * 100) if total_chats > 0 else None
        )

        # first_attempt_pass_rate for this profile
        completed_items = [
            i for i in items if i.completed and i.attempt_date is not None
        ]
        first_attempt_pass_rate_val = None
        if completed_items:
            first_completed = min(completed_items, key=lambda i: i.attempt_date)  # type: ignore[arg-type]
            first_attempt_pass_rate_val = 100.0 if first_completed.grade_passed else 0.0

        # Collect simulation_ids and scenario_ids for this profile
        sim_ids = list({str(i.simulation_id) for i in items})
        scen_ids = list(
            {str(i.scenario_id) for i in items if i.scenario_id is not None}
        )

        rows.append(
            ReportsLeaderboardRow(
                rank=index + 1,
                profile_id=pid,
                total_attempts=attempt_count,
                average_score=avg_score,
                highest_score=highest_score,
                completion_percentage=completion_pct,
                first_attempt_pass_rate=_round2(first_attempt_pass_rate_val),
                profile_metrics=_build_profile_metrics_v2(
                    profile_id=pid,
                    items=items,
                    thresholds=thresholds,
                    stagnation_stats=stagnation_stats,
                ),
                simulation_ids=sim_ids,
                scenario_ids=scen_ids,
            )
        )

    return ReportsLeaderboardSection(
        status=_section(bool(rows), "Derived from mv_profile_facts"),
        rows=rows,
    )


def compute_trends_section_v2(
    profile_facts_items: list[ChatItem],
) -> ReportsTrendsSection:
    """Compute daily trend points from ChatItem rows."""
    grouped: dict[date, dict[str, float]] = defaultdict(
        lambda: {
            "total": 0.0,
            "completed": 0.0,
            "passed": 0.0,
            "score_sum": 0.0,
            "score_n": 0.0,
        }
    )

    # We need distinct attempt_ids per date for "attempts" count
    date_attempt_ids: dict[date, set] = defaultdict(set)

    for item in profile_facts_items:
        if item.attempt_date is None:
            continue
        d = item.attempt_date
        date_attempt_ids[d].add(item.attempt_id)
        bucket = grouped[d]
        bucket["total"] += 1
        if item.completed:
            bucket["completed"] += 1
        if item.grade_passed:
            bucket["passed"] += 1
        if item.grade_percent is not None:
            bucket["score_sum"] += float(item.grade_percent)
            bucket["score_n"] += 1

    points: list[ReportsTrendPoint] = []
    for day in sorted(grouped.keys()):
        bucket = grouped[day]
        attempts_n = len(date_attempt_ids[day])
        completed_n = int(bucket["completed"])
        passed_n = int(bucket["passed"])
        date_total = int(bucket["total"])
        avg_score = (
            bucket["score_sum"] / bucket["score_n"] if bucket["score_n"] > 0 else None
        )
        completion_pct = (completed_n / date_total) * 100 if date_total > 0 else None
        pass_rate = (passed_n / date_total) * 100 if date_total > 0 else None
        points.append(
            ReportsTrendPoint(
                date=_date_str(day),
                attempts=attempts_n,
                completed_attempts=completed_n,
                passed_attempts=passed_n,
                average_score=_round2(avg_score),
                completion_percentage=_round2(completion_pct),
                pass_rate=_round2(pass_rate),
            )
        )

    return ReportsTrendsSection(
        status=_section(bool(points), "Derived from mv_profile_facts"),
        chart_data=points,
    )


def compute_history_section_v2(
    profile_facts_items: list[ChatItem],
) -> ReportsHistorySection:
    """Compute history rows from ChatItem rows, grouped by attempt_id."""
    # Group by attempt_id
    attempt_chats: dict[str, list[ChatItem]] = defaultdict(list)
    for item in profile_facts_items:
        attempt_chats[str(item.attempt_id)].append(item)

    rows: list[ReportsHistoryRow] = []
    for attempt_id, chats in attempt_chats.items():
        first = chats[0]

        # attempt_created_at: convert date to datetime
        attempt_created_at: datetime | None = None
        if first.attempt_date is not None:
            attempt_created_at = datetime.combine(
                first.attempt_date, datetime.min.time()
            )

        # score_percent: avg grade_percent across chats in attempt
        chat_scores = [
            float(c.grade_percent) for c in chats if c.grade_percent is not None
        ]
        score_percent = (
            _round2(sum(chat_scores) / len(chat_scores)) if chat_scores else None
        )

        # has_passed: any chat passed
        has_passed = any(c.grade_passed for c in chats if c.grade_passed is not None)

        # num_chats and num_chats_completed
        num_chats = len(chats)
        num_chats_completed = sum(1 for c in chats if c.completed)

        # total_time_seconds
        total_time_seconds = sum(
            c.grade_time_taken for c in chats if c.grade_time_taken is not None
        )

        # scenario_ids: distinct scenario_ids from chats
        scenario_ids = list(
            {str(c.scenario_id) for c in chats if c.scenario_id is not None}
        )

        rows.append(
            ReportsHistoryRow(
                attempt_id=attempt_id,
                profile_id=str(first.profile_id),
                simulation_id=str(first.simulation_id),
                cohort_id=str(first.cohort_id) if first.cohort_id else None,
                attempt_created_at=attempt_created_at,
                attempt_type=first.attempt_type,
                is_archived=first.is_archived,
                infinite_mode=first.infinite_mode,
                score_percent=score_percent,
                has_passed=has_passed,
                num_chats=num_chats,
                num_chats_completed=num_chats_completed,
                total_time_seconds=total_time_seconds,
                scenario_ids=scenario_ids,
            )
        )

    # Sort by attempt_created_at descending
    rows.sort(
        key=lambda row: (
            row.attempt_created_at
            if row.attempt_created_at is not None
            else datetime.min
        ),
        reverse=True,
    )

    return ReportsHistorySection(
        status=_section(bool(rows), "Derived from mv_profile_facts"),
        rows=rows,
    )


def build_reports_sections_v2(
    profile_facts_items: list[ChatItem],
    total_count: int = 0,
    thresholds: dict[str, int] | None = None,
) -> ReportsSections:
    """Build section-computation skeleton for reports artifact from mv_profile_facts.

    Single-MV replacement for build_reports_sections which required 4 separate MVs.
    """
    header_metrics = compute_reports_header_metrics_v2(
        profile_facts_items=profile_facts_items,
        total_count=total_count,
        thresholds=thresholds,
    )

    return ReportsSections(
        header_metrics=header_metrics,
        overview=compute_overview_section_v2(profile_facts_items=profile_facts_items),
        leaderboard=compute_leaderboard_section_v2(
            profile_facts_items=profile_facts_items,
            thresholds=thresholds,
        ),
        trends=compute_trends_section_v2(profile_facts_items=profile_facts_items),
        history=compute_history_section_v2(profile_facts_items=profile_facts_items),
    )
