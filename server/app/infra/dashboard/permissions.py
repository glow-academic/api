"""Dashboard calculation/business logic for get.py."""

from collections import defaultdict
from datetime import date
from statistics import mean
from typing import Any

from app.infra.dashboard.context import RubricScoreItem
from app.infra.dashboard.types import (
    DashboardBundleResponse,
    DashboardFooterMetrics,
    DashboardHeaderMetric,
    DashboardHeaderMetrics,
    DashboardPrimaryMetrics,
    DashboardSecondaryMetrics,
)
from app.tools.entries.attempt_chat.types import ChatItem

# Compat aliases for old type annotations — all now use ChatItem
ProfileFactsItem = ChatItem
ScenarioFactsItem = ChatItem
SimulationFactsItem = ChatItem
RubricFactsItem = RubricScoreItem

# Type aliases for removed analytics types (used by deprecated v1 functions below)
AttemptFactsItem = Any
ChatFactsItem = Any
DailyMetricsItem = Any
FirstAttemptPassItem = Any
ProfileMetricsItem = Any
RubricGroupScoreItem = Any


def _empty_header_metric() -> DashboardHeaderMetric:
    return DashboardHeaderMetric(
        current_value=0,
        trend_data=[],
        has_data=False,
        trend_analysis="Insufficient data",
        status="neutral",
    )


def _round2(value: float | int | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _weighted_average(pairs: list[tuple[float | int | None, int]]) -> float | None:
    usable = [(float(v), w) for v, w in pairs if v is not None and w > 0]
    if not usable:
        return None
    total_weight = sum(w for _, w in usable)
    if total_weight == 0:
        return None
    return sum(v * w for v, w in usable) / total_weight


def _build_trend_analysis(
    trend_values: list[float | None],
    lower_is_better: bool = False,
) -> str:
    usable = [v for v in trend_values if v is not None]
    if len(usable) < 2:
        return "Insufficient data"

    start = usable[0]
    end = usable[-1]
    delta = end - start

    if abs(delta) < 1e-9:
        return "Flat trend"

    if start == 0:
        direction = "up" if delta > 0 else "down"
        if lower_is_better:
            direction = "down" if delta > 0 else "up"
        return f"{direction.capitalize()} {abs(delta):.2f} vs period start"

    pct = (delta / abs(start)) * 100
    direction = "up" if pct > 0 else "down"
    if lower_is_better:
        direction = "down" if pct > 0 else "up"
    return f"{direction.capitalize()} {abs(pct):.1f}% vs period start"


def _status_from_thresholds(
    value: float | int | None,
    success_threshold: float,
    warning_threshold: float,
    lower_is_better: bool = False,
) -> str:
    if value is None:
        return "neutral"
    n = float(value)
    if lower_is_better:
        if n <= success_threshold:
            return "success"
        if n <= warning_threshold:
            return "warning"
        return "danger"
    if n >= success_threshold:
        return "success"
    if n >= warning_threshold:
        return "warning"
    return "danger"


def _iso(d: date) -> str:
    return d.isoformat()


def _section_status(has_data: bool) -> str:
    return "success" if has_data else "neutral"


def _thresholds(thresholds: dict[str, int] | None) -> tuple[int, int, int]:
    if not thresholds:
        return (85, 80, 70)
    return (
        int(thresholds.get("success", 85)),
        int(thresholds.get("warning", 80)),
        int(thresholds.get("danger", 70)),
    )


def compute_header_metrics(
    attempts: list[AttemptFactsItem],
    daily_rows: list[DailyMetricsItem],
    chat_rows: list[ChatFactsItem],
    profile_rows: list[ProfileMetricsItem],
    first_attempt_rows: list[FirstAttemptPassItem] | None = None,
    simulation_scenario_counts: dict[str, int] | None = None,
    thresholds: dict[str, int] | None = None,
) -> DashboardHeaderMetrics:
    """Compute header metrics from raw MV rows."""
    if not (attempts or daily_rows or chat_rows or profile_rows):
        return DashboardHeaderMetrics(
            average_score=_empty_header_metric(),
            completion_percentage=_empty_header_metric(),
            first_attempt_pass_rate=_empty_header_metric(),
            highest_score=_empty_header_metric(),
            messages_per_session=_empty_header_metric(),
            persona_response_times=_empty_header_metric(),
            session_efficiency=_empty_header_metric(),
            stagnation_rate=_empty_header_metric(),
            time_spent=_empty_header_metric(),
            total_attempts=_empty_header_metric(),
        )

    success_threshold, warning_threshold, danger_threshold = _thresholds(thresholds)
    first_attempt_rows = first_attempt_rows or []
    simulation_scenario_counts = simulation_scenario_counts or {}

    daily_by_date: dict[date, dict[str, float]] = defaultdict(
        lambda: {
            "attempts": 0.0,
            "completed": 0.0,
            "passed": 0.0,
            "sum_score_weighted": 0.0,
            "score_weight": 0.0,
            "sum_messages_weighted": 0.0,
            "message_weight": 0.0,
            "time_seconds": 0.0,
        }
    )
    for row in daily_rows:
        bucket = daily_by_date[row.date_key]
        attempts_count = float(row.attempt_count or 0)
        bucket["attempts"] += attempts_count
        bucket["completed"] += float(row.completed_count or 0)
        bucket["passed"] += float(row.passed_count or 0)
        bucket["time_seconds"] += float(row.total_time_seconds or 0)
        if row.avg_score is not None and attempts_count > 0:
            bucket["sum_score_weighted"] += float(row.avg_score) * attempts_count
            bucket["score_weight"] += attempts_count
        if row.avg_messages is not None and attempts_count > 0:
            bucket["sum_messages_weighted"] += float(row.avg_messages) * attempts_count
            bucket["message_weight"] += attempts_count

    attempt_high_by_date: dict[date, float] = {}
    attempt_counts_by_date: dict[date, int] = defaultdict(int)
    for attempt in attempts:
        if attempt.attempt_created_at is None:
            continue
        d = attempt.attempt_created_at.date()
        attempt_counts_by_date[d] += 1
        if attempt.score_percent is None:
            continue
        score = float(attempt.score_percent)
        current = attempt_high_by_date.get(d)
        attempt_high_by_date[d] = score if current is None else max(current, score)

    response_time_by_date: dict[date, list[float]] = defaultdict(list)
    for row in chat_rows:
        d = row.chat_created_at.date()
        times = [float(t) for t in row.message_time_taken_seconds if t is not None]
        if not times:
            continue
        response_time_by_date[d].append(mean(times))

    first_attempt_by_date: dict[date, dict[str, float]] = defaultdict(
        lambda: {"passed": 0.0, "total": 0.0}
    )
    for item in first_attempt_rows:
        d = item.attempt_created_at.date()
        first_attempt_by_date[d]["total"] += 1.0
        pass_threshold = None
        if item.rubric_pass_points is not None and item.rubric_total_points:
            pass_threshold = (
                float(item.rubric_pass_points) * 100.0 / float(item.rubric_total_points)
            )
        is_pass = (
            item.grade_percent is not None
            and pass_threshold is not None
            and float(item.grade_percent) >= pass_threshold
        )
        first_attempt_by_date[d]["passed"] += 1.0 if is_pass else 0.0

    chats_by_date: dict[date, list[ChatFactsItem]] = defaultdict(list)
    for row in chat_rows:
        chats_by_date[row.attempt_created_at.date()].append(row)

    # Beta parity: normalized average score per attempt
    # norm = sum(grade_percent) / max(expected_sim_scenarios, chats_in_attempt)
    # only when completed_chats == graded_chats and completed_chats > 0
    attempt_chat_agg: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "attempt_created_at": None,
            "simulation_id": None,
            "completed_chats": 0,
            "graded_chats": 0,
            "chats_in_attempt": 0,
            "sum_grade_percent": 0.0,
        }
    )
    for row in chat_rows:
        aid = str(row.attempt_id)
        a = attempt_chat_agg[aid]
        a["attempt_created_at"] = row.attempt_created_at
        a["simulation_id"] = str(row.simulation_id)
        a["chats_in_attempt"] += 1
        if row.completed:
            a["completed_chats"] += 1
        if row.completed and row.grade_percent is not None:
            a["graded_chats"] += 1
        if row.grade_percent is not None:
            a["sum_grade_percent"] += float(row.grade_percent)

    attempt_norm_by_date: dict[date, list[float]] = defaultdict(list)
    for a in attempt_chat_agg.values():
        created_at = a["attempt_created_at"]
        simulation_id = a["simulation_id"]
        if created_at is None or simulation_id is None:
            continue
        expected_from_sim = int(simulation_scenario_counts.get(simulation_id, 0))
        chats_in_attempt = int(a["chats_in_attempt"])
        expected = max(expected_from_sim, chats_in_attempt)
        completed_chats = int(a["completed_chats"])
        graded_chats = int(a["graded_chats"])
        if expected > 0 and completed_chats > 0 and completed_chats == graded_chats:
            norm = float(a["sum_grade_percent"]) / float(expected)
            attempt_norm_by_date[created_at.date()].append(norm)

    daily_dates = sorted(daily_by_date.keys())
    all_dates = sorted(
        set(daily_dates)
        | set(attempt_counts_by_date.keys())
        | set(response_time_by_date.keys())
    )

    avg_score_trend = []
    completion_trend = []
    first_pass_trend = []
    messages_trend = []
    session_efficiency_trend = []
    time_spent_trend = []
    total_attempts_trend = []
    highest_score_trend = []
    response_time_trend = []

    for d in all_dates:
        bucket = daily_by_date.get(d)
        attempts_count = (
            int(bucket["attempts"]) if bucket else attempt_counts_by_date.get(d, 0)
        )
        completed_count = int(bucket["completed"]) if bucket else 0

        avg_score_vals = attempt_norm_by_date.get(d, [])
        avg_score_val = mean(avg_score_vals) if avg_score_vals else None

        completion_val = (
            (completed_count / attempts_count) * 100 if attempts_count > 0 else None
        )
        first_day = first_attempt_by_date.get(d)
        first_pass_val = (
            (first_day["passed"] / first_day["total"]) * 100
            if first_day and first_day["total"] > 0
            else None
        )

        avg_messages_val = None
        if bucket and bucket["message_weight"] > 0:
            avg_messages_val = (
                bucket["sum_messages_weighted"] / bucket["message_weight"]
            )

        # Beta parity formulas:
        # session_efficiency = avgScore * (1 - min(1, avgMinutesPerSession/120)), clamped 0..100
        # time_spent trend uses AVG(LEAST(chat_minutes, 30))
        day_chats = chats_by_date.get(d, [])
        day_scores = [
            float(c.grade_percent) for c in day_chats if c.grade_percent is not None
        ]
        day_minutes = [
            float(c.time_taken or 0) / 60.0
            for c in day_chats
            if c.time_taken is not None
        ]
        session_efficiency_val = None
        if day_scores and day_minutes:
            avg_score_day = mean(day_scores)
            avg_min_day = sum(day_minutes) / len(day_minutes)
            session_efficiency_val = max(
                0.0,
                min(100.0, avg_score_day * (1.0 - min(1.0, avg_min_day / 120.0))),
            )
        time_spent_min_val = (
            (sum(min(m, 30.0) for m in day_minutes) / len(day_minutes))
            if day_minutes
            else None
        )

        avg_score_trend.append(
            {
                "date": _iso(d),
                "value": _round2(avg_score_val),
                "count": len(avg_score_vals),
            }
        )
        completion_trend.append(
            {"date": _iso(d), "value": _round2(completion_val), "count": attempts_count}
        )
        first_pass_trend.append(
            {
                "date": _iso(d),
                "value": _round2(first_pass_val),
                "count": completed_count,
            }
        )
        messages_trend.append(
            {
                "date": _iso(d),
                "value": _round2(avg_messages_val),
                "count": attempts_count,
            }
        )
        session_efficiency_trend.append(
            {
                "date": _iso(d),
                "value": _round2(session_efficiency_val),
                "count": attempts_count,
            }
        )
        time_spent_trend.append(
            {
                "date": _iso(d),
                "value": _round2(time_spent_min_val),
                "count": attempts_count,
            }
        )
        total_attempts_trend.append(
            {"date": _iso(d), "value": float(attempts_count), "count": attempts_count}
        )
        highest_score_trend.append(
            {
                "date": _iso(d),
                "value": _round2(attempt_high_by_date.get(d)),
                "count": attempt_counts_by_date.get(d, attempts_count),
            }
        )

        rt_values = response_time_by_date.get(d, [])
        response_time_trend.append(
            {
                "date": _iso(d),
                "value": _round2(mean(rt_values)) if rt_values else None,
                "count": len(rt_values),
            }
        )

    stagnation_trend = []
    prev_score: float | None = None
    for point in avg_score_trend:
        cur = point["value"]
        if cur is None or prev_score is None:
            stagnation_val = None
        else:
            stagnation_val = 100.0 if cur <= prev_score else 0.0
        stagnation_trend.append(
            {"date": point["date"], "value": _round2(stagnation_val), "count": 1}
        )
        if cur is not None:
            prev_score = cur

    total_attempts_value = len(attempts)
    all_norms = [v for vals in attempt_norm_by_date.values() for v in vals]
    average_score_value = _round2(mean(all_norms)) if all_norms else None
    completion_pct_value = _round2(
        ((sum(1 for c in chat_rows if c.completed) / len(chat_rows)) * 100)
        if chat_rows
        else None
    )
    first_total = len(first_attempt_rows)
    first_passed = 0
    for item in first_attempt_rows:
        if (
            item.grade_percent is None
            or item.rubric_pass_points is None
            or not item.rubric_total_points
        ):
            continue
        pass_threshold = (
            float(item.rubric_pass_points) * 100.0 / float(item.rubric_total_points)
        )
        if float(item.grade_percent) >= pass_threshold:
            first_passed += 1
    first_attempt_pass_rate_value = _round2(
        (first_passed / first_total * 100.0) if first_total > 0 else None
    )
    highest_score_value = _round2(
        max(
            (a.score_percent for a in attempts if a.score_percent is not None),
            default=None,
        )
    )
    messages_per_session_value = _round2(
        _weighted_average([(d.avg_messages, d.attempt_count) for d in daily_rows])
    )
    persona_response_time_value = _round2(
        _weighted_average(
            [
                (p.avg_persona_response_sec, max(p.total_attempts, 1))
                for p in profile_rows
            ]
        )
    )
    all_scores = [
        float(c.grade_percent) for c in chat_rows if c.grade_percent is not None
    ]
    all_minutes = [
        float(c.time_taken or 0) / 60.0 for c in chat_rows if c.time_taken is not None
    ]
    session_efficiency_value = None
    if all_scores and all_minutes:
        avg_score_all = mean(all_scores)
        avg_minutes_per_session = sum(all_minutes) / len(all_minutes)
        session_efficiency_value = _round2(
            max(
                0.0,
                min(
                    100.0,
                    avg_score_all * (1.0 - min(1.0, avg_minutes_per_session / 120.0)),
                ),
            )
        )
    time_spent_minutes_value = _round2(
        sum(
            min((c.time_taken or 0) / 60.0, 30.0)
            for c in chat_rows
            if c.time_taken is not None
        )
        if chat_rows
        else None
    )
    stagnation_rate_value = _round2(
        mean([p["value"] for p in stagnation_trend if p["value"] is not None])
        if any(p["value"] is not None for p in stagnation_trend)
        else None
    )

    def metric(
        value: float | int | None,
        trend_data: list[dict],
        success_threshold: float,
        warning_threshold: float,
        lower_is_better: bool = False,
    ) -> DashboardHeaderMetric:
        trend_values = [p["value"] for p in trend_data]
        has_data = value is not None and any(v is not None for v in trend_values)
        return DashboardHeaderMetric(
            current_value=value if value is not None else 0,
            trend_data=trend_data,
            has_data=has_data,
            trend_analysis=_build_trend_analysis(
                trend_values=trend_values, lower_is_better=lower_is_better
            ),
            status=(
                _status_from_thresholds(
                    value=value,
                    success_threshold=success_threshold,
                    warning_threshold=warning_threshold,
                    lower_is_better=lower_is_better,
                )
                if value is not None
                else "neutral"
            ),
        )

    return DashboardHeaderMetrics(
        average_score=metric(
            value=average_score_value,
            trend_data=avg_score_trend,
            success_threshold=success_threshold,
            warning_threshold=warning_threshold,
        ),
        completion_percentage=metric(
            value=completion_pct_value,
            trend_data=completion_trend,
            success_threshold=success_threshold,
            warning_threshold=warning_threshold,
        ),
        first_attempt_pass_rate=metric(
            value=first_attempt_pass_rate_value,
            trend_data=first_pass_trend,
            success_threshold=success_threshold,
            warning_threshold=warning_threshold,
        ),
        highest_score=metric(
            value=highest_score_value,
            trend_data=highest_score_trend,
            success_threshold=success_threshold,
            warning_threshold=warning_threshold,
        ),
        messages_per_session=metric(
            value=messages_per_session_value,
            trend_data=messages_trend,
            success_threshold=success_threshold,
            warning_threshold=warning_threshold,
        ),
        persona_response_times=metric(
            value=persona_response_time_value,
            trend_data=response_time_trend,
            success_threshold=danger_threshold,
            warning_threshold=warning_threshold,
            lower_is_better=True,
        ),
        session_efficiency=metric(
            value=session_efficiency_value,
            trend_data=session_efficiency_trend,
            success_threshold=success_threshold,
            warning_threshold=warning_threshold,
        ),
        stagnation_rate=metric(
            value=stagnation_rate_value,
            trend_data=stagnation_trend,
            success_threshold=danger_threshold,
            warning_threshold=warning_threshold,
            lower_is_better=True,
        ),
        time_spent=metric(
            value=time_spent_minutes_value,
            trend_data=time_spent_trend,
            success_threshold=success_threshold,
            warning_threshold=warning_threshold,
        ),
        total_attempts=metric(
            value=total_attempts_value,
            trend_data=total_attempts_trend,
            success_threshold=1,
            warning_threshold=1,
        ),
    )


def compute_header_metrics_v2(
    profile_facts_items: list[ProfileFactsItem],
    simulation_scenario_counts: dict[str, int] | None = None,
    thresholds: dict[str, int] | None = None,
) -> DashboardHeaderMetrics:
    """Compute header metrics from profile_facts chat-grain rows.

    This is the v2 replacement for compute_header_metrics() that derives all
    10 header metrics from a single mv_profile_facts data source instead of
    5 separate MVs (attempt_facts, chat_facts, daily_metrics, profile_metrics,
    first_attempt_pass).
    """
    if not profile_facts_items:
        return DashboardHeaderMetrics(
            average_score=_empty_header_metric(),
            completion_percentage=_empty_header_metric(),
            first_attempt_pass_rate=_empty_header_metric(),
            highest_score=_empty_header_metric(),
            messages_per_session=_empty_header_metric(),
            persona_response_times=_empty_header_metric(),
            session_efficiency=_empty_header_metric(),
            stagnation_rate=_empty_header_metric(),
            time_spent=_empty_header_metric(),
            total_attempts=_empty_header_metric(),
        )

    success_threshold, warning_threshold, danger_threshold = _thresholds(thresholds)
    simulation_scenario_counts = simulation_scenario_counts or {}

    # ── Data preparation ──────────────────────────────────────────────

    # Group items by attempt_date
    items_by_date: dict[date, list[ProfileFactsItem]] = defaultdict(list)
    for item in profile_facts_items:
        if item.attempt_date is not None:
            items_by_date[item.attempt_date].append(item)

    # Group items by attempt_id for normalized avg score
    attempt_chat_agg: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "attempt_date": None,
            "simulation_id": None,
            "completed_chats": 0,
            "graded_chats": 0,
            "chats_in_attempt": 0,
            "sum_grade_percent": 0.0,
        }
    )
    for item in profile_facts_items:
        aid = str(item.attempt_id)
        a = attempt_chat_agg[aid]
        a["attempt_date"] = item.attempt_date
        a["simulation_id"] = str(item.simulation_id)
        a["chats_in_attempt"] += 1
        if item.completed:
            a["completed_chats"] += 1
        if item.completed and item.grade_percent is not None:
            a["graded_chats"] += 1
        if item.grade_percent is not None:
            a["sum_grade_percent"] += float(item.grade_percent)

    # Normalized avg score per attempt, grouped by date
    attempt_norm_by_date: dict[date, list[float]] = defaultdict(list)
    for a in attempt_chat_agg.values():
        attempt_date = a["attempt_date"]
        simulation_id = a["simulation_id"]
        if attempt_date is None or simulation_id is None:
            continue
        expected_from_sim = int(simulation_scenario_counts.get(simulation_id, 0))
        chats_in_attempt = int(a["chats_in_attempt"])
        expected = max(expected_from_sim, chats_in_attempt)
        completed_chats = int(a["completed_chats"])
        graded_chats = int(a["graded_chats"])
        if expected > 0 and completed_chats > 0 and completed_chats == graded_chats:
            norm = float(a["sum_grade_percent"]) / float(expected)
            attempt_norm_by_date[attempt_date].append(norm)

    # First attempt pass: for each profile, find earliest completed chat
    profile_first_attempts: dict[str, ProfileFactsItem] = {}
    for item in profile_facts_items:
        if not item.completed:
            continue
        pid = str(item.profile_id)
        existing = profile_first_attempts.get(pid)
        if existing is None:
            profile_first_attempts[pid] = item
        else:
            # Compare by attempt_date first, then chat_id for tie-breaking
            if item.attempt_date is not None and (
                existing.attempt_date is None
                or item.attempt_date < existing.attempt_date
                or (
                    item.attempt_date == existing.attempt_date
                    and str(item.chat_id) < str(existing.chat_id)
                )
            ):
                profile_first_attempts[pid] = item

    # First attempt pass by date
    first_attempt_by_date: dict[date, dict[str, float]] = defaultdict(
        lambda: {"passed": 0.0, "total": 0.0}
    )
    for item in profile_first_attempts.values():
        if item.attempt_date is not None:
            d = item.attempt_date
            first_attempt_by_date[d]["total"] += 1.0
            if item.passed:
                first_attempt_by_date[d]["passed"] += 1.0

    # ── Build trend data ──────────────────────────────────────────────

    all_dates = sorted(items_by_date.keys())

    avg_score_trend = []
    completion_trend = []
    first_pass_trend = []
    messages_trend = []
    session_efficiency_trend = []
    time_spent_trend = []
    total_attempts_trend = []
    highest_score_trend = []
    response_time_trend = []

    for d in all_dates:
        day_items = items_by_date[d]

        # total_attempts: count distinct attempt_ids this date
        day_attempt_ids = {str(item.attempt_id) for item in day_items}
        attempts_count = len(day_attempt_ids)

        # completion: count completed / total chats
        completed_count = sum(1 for item in day_items if item.completed)
        completion_val = (
            (completed_count / len(day_items)) * 100 if len(day_items) > 0 else None
        )

        # avg_score: from normalized attempt scores
        avg_score_vals = attempt_norm_by_date.get(d, [])
        avg_score_val = mean(avg_score_vals) if avg_score_vals else None

        # first_attempt_pass_rate
        first_day = first_attempt_by_date.get(d)
        first_pass_val = (
            (first_day["passed"] / first_day["total"]) * 100
            if first_day and first_day["total"] > 0
            else None
        )

        # highest_score: max grade_percent for this date
        day_grades = [
            float(item.grade_percent)
            for item in day_items
            if item.grade_percent is not None
        ]
        highest_score_val = max(day_grades) if day_grades else None

        # messages_per_session: avg num_messages_total
        day_messages = [float(item.num_messages_total) for item in day_items]
        avg_messages_val = mean(day_messages) if day_messages else None

        # persona_response_times: avg of avg_response_sec
        day_response_secs = [
            float(item.avg_response_sec)
            for item in day_items
            if item.avg_response_sec is not None
        ]
        response_time_val = mean(day_response_secs) if day_response_secs else None

        # session_efficiency: avg_score * (1 - min(1, avg_minutes / 120)), clamped 0..100
        day_scores = [
            float(item.grade_percent)
            for item in day_items
            if item.grade_percent is not None
        ]
        day_minutes = [
            float(item.time_taken_seconds) / 60.0
            for item in day_items
            if item.time_taken_seconds is not None
        ]
        session_efficiency_val = None
        if day_scores and day_minutes:
            avg_score_day = mean(day_scores)
            avg_min_day = mean(day_minutes)
            session_efficiency_val = max(
                0.0,
                min(100.0, avg_score_day * (1.0 - min(1.0, avg_min_day / 120.0))),
            )

        # time_spent: avg(min(time_taken_seconds/60, 30))
        time_spent_min_val = (
            mean([min(m, 30.0) for m in day_minutes]) if day_minutes else None
        )

        avg_score_trend.append(
            {
                "date": _iso(d),
                "value": _round2(avg_score_val),
                "count": len(avg_score_vals),
            }
        )
        completion_trend.append(
            {
                "date": _iso(d),
                "value": _round2(completion_val),
                "count": len(day_items),
            }
        )
        first_pass_trend.append(
            {
                "date": _iso(d),
                "value": _round2(first_pass_val),
                "count": completed_count,
            }
        )
        messages_trend.append(
            {
                "date": _iso(d),
                "value": _round2(avg_messages_val),
                "count": len(day_items),
            }
        )
        session_efficiency_trend.append(
            {
                "date": _iso(d),
                "value": _round2(session_efficiency_val),
                "count": attempts_count,
            }
        )
        time_spent_trend.append(
            {
                "date": _iso(d),
                "value": _round2(time_spent_min_val),
                "count": attempts_count,
            }
        )
        total_attempts_trend.append(
            {"date": _iso(d), "value": float(attempts_count), "count": attempts_count}
        )
        highest_score_trend.append(
            {
                "date": _iso(d),
                "value": _round2(highest_score_val),
                "count": attempts_count,
            }
        )
        response_time_trend.append(
            {
                "date": _iso(d),
                "value": _round2(response_time_val),
                "count": len(day_response_secs),
            }
        )

    # Stagnation trend: compare consecutive avg_score trend points
    stagnation_trend = []
    prev_score: float | None = None
    for point in avg_score_trend:
        cur = point["value"]
        if cur is None or prev_score is None:
            stagnation_val = None
        else:
            stagnation_val = 100.0 if cur <= prev_score else 0.0
        stagnation_trend.append(
            {"date": point["date"], "value": _round2(stagnation_val), "count": 1}
        )
        if cur is not None:
            prev_score = cur

    # ── Overall values ────────────────────────────────────────────────

    # 1. total_attempts
    total_attempts_value = len({str(item.attempt_id) for item in profile_facts_items})

    # 2. average_score (normalized)
    all_norms = [v for vals in attempt_norm_by_date.values() for v in vals]
    average_score_value = _round2(mean(all_norms)) if all_norms else None

    # 3. completion_percentage
    completion_pct_value = _round2(
        (
            sum(1 for item in profile_facts_items if item.completed)
            / len(profile_facts_items)
        )
        * 100
    )

    # 4. first_attempt_pass_rate
    first_total = len(profile_first_attempts)
    first_passed = sum(1 for item in profile_first_attempts.values() if item.passed)
    first_attempt_pass_rate_value = _round2(
        (first_passed / first_total * 100.0) if first_total > 0 else None
    )

    # 5. highest_score
    highest_score_value = _round2(
        max(
            (
                float(item.grade_percent)
                for item in profile_facts_items
                if item.grade_percent is not None
            ),
            default=None,
        )
    )

    # 6. messages_per_session
    messages_per_session_value = _round2(
        mean([float(item.num_messages_total) for item in profile_facts_items])
        if profile_facts_items
        else None
    )

    # 7. persona_response_times
    response_secs = [
        float(item.avg_response_sec)
        for item in profile_facts_items
        if item.avg_response_sec is not None
    ]
    persona_response_time_value = _round2(
        mean(response_secs) if response_secs else None
    )

    # 8. session_efficiency
    all_scores = [
        float(item.grade_percent)
        for item in profile_facts_items
        if item.grade_percent is not None
    ]
    all_minutes = [
        float(item.time_taken_seconds) / 60.0
        for item in profile_facts_items
        if item.time_taken_seconds is not None
    ]
    session_efficiency_value = None
    if all_scores and all_minutes:
        avg_score_all = mean(all_scores)
        avg_minutes_per_session = mean(all_minutes)
        session_efficiency_value = _round2(
            max(
                0.0,
                min(
                    100.0,
                    avg_score_all * (1.0 - min(1.0, avg_minutes_per_session / 120.0)),
                ),
            )
        )

    # 9. time_spent: avg(min(time_taken_seconds/60, 30))
    time_spent_minutes_value = _round2(
        mean([min(m, 30.0) for m in all_minutes]) if all_minutes else None
    )

    # 10. stagnation_rate
    stagnation_rate_value = _round2(
        mean([p["value"] for p in stagnation_trend if p["value"] is not None])
        if any(p["value"] is not None for p in stagnation_trend)
        else None
    )

    # ── Build metric objects ──────────────────────────────────────────

    def metric(
        value: float | int | None,
        trend_data: list[dict],
        success_threshold_val: float,
        warning_threshold_val: float,
        lower_is_better: bool = False,
    ) -> DashboardHeaderMetric:
        trend_values = [p["value"] for p in trend_data]
        has_data = value is not None and any(v is not None for v in trend_values)
        return DashboardHeaderMetric(
            current_value=value if value is not None else 0,
            trend_data=trend_data,
            has_data=has_data,
            trend_analysis=_build_trend_analysis(
                trend_values=trend_values, lower_is_better=lower_is_better
            ),
            status=(
                _status_from_thresholds(
                    value=value,
                    success_threshold=success_threshold_val,
                    warning_threshold=warning_threshold_val,
                    lower_is_better=lower_is_better,
                )
                if value is not None
                else "neutral"
            ),
        )

    return DashboardHeaderMetrics(
        average_score=metric(
            value=average_score_value,
            trend_data=avg_score_trend,
            success_threshold_val=success_threshold,
            warning_threshold_val=warning_threshold,
        ),
        completion_percentage=metric(
            value=completion_pct_value,
            trend_data=completion_trend,
            success_threshold_val=success_threshold,
            warning_threshold_val=warning_threshold,
        ),
        first_attempt_pass_rate=metric(
            value=first_attempt_pass_rate_value,
            trend_data=first_pass_trend,
            success_threshold_val=success_threshold,
            warning_threshold_val=warning_threshold,
        ),
        highest_score=metric(
            value=highest_score_value,
            trend_data=highest_score_trend,
            success_threshold_val=success_threshold,
            warning_threshold_val=warning_threshold,
        ),
        messages_per_session=metric(
            value=messages_per_session_value,
            trend_data=messages_trend,
            success_threshold_val=success_threshold,
            warning_threshold_val=warning_threshold,
        ),
        persona_response_times=metric(
            value=persona_response_time_value,
            trend_data=response_time_trend,
            success_threshold_val=danger_threshold,
            warning_threshold_val=warning_threshold,
            lower_is_better=True,
        ),
        session_efficiency=metric(
            value=session_efficiency_value,
            trend_data=session_efficiency_trend,
            success_threshold_val=success_threshold,
            warning_threshold_val=warning_threshold,
        ),
        stagnation_rate=metric(
            value=stagnation_rate_value,
            trend_data=stagnation_trend,
            success_threshold_val=danger_threshold,
            warning_threshold_val=warning_threshold,
            lower_is_better=True,
        ),
        time_spent=metric(
            value=time_spent_minutes_value,
            trend_data=time_spent_trend,
            success_threshold_val=success_threshold,
            warning_threshold_val=warning_threshold,
        ),
        total_attempts=metric(
            value=total_attempts_value,
            trend_data=total_attempts_trend,
            success_threshold_val=1,
            warning_threshold_val=1,
        ),
    )


def compute_primary_metrics(
    attempts: list[AttemptFactsItem],
    daily_rows: list[DailyMetricsItem],
    chat_rows: list[ChatFactsItem],
    profile_rows: list[ProfileMetricsItem],
    rubric_group_scores: list[RubricGroupScoreItem] | None = None,
    persona_name_map: dict[str, str] | None = None,
    thresholds: dict[str, int] | None = None,
) -> DashboardPrimaryMetrics:
    """Compute primary section metrics for dashboard get bundle."""
    _ = profile_rows
    _ = attempts
    success_threshold, warning_threshold, _danger_threshold = _thresholds(thresholds)
    rubric_group_scores = rubric_group_scores or []

    # Growth
    daily_group: dict[date, dict[str, float]] = defaultdict(
        lambda: {
            "attempts": 0.0,
            "completed": 0.0,
            "passed": 0.0,
            "sum_score_weighted": 0.0,
            "score_weight": 0.0,
            "time_seconds": 0.0,
        }
    )
    for row in daily_rows:
        b = daily_group[row.date_key]
        at = float(row.attempt_count or 0)
        b["attempts"] += at
        b["completed"] += float(row.completed_count or 0)
        b["passed"] += float(row.passed_count or 0)
        b["time_seconds"] += float(row.total_time_seconds or 0)
        if row.avg_score is not None and at > 0:
            b["sum_score_weighted"] += float(row.avg_score) * at
            b["score_weight"] += at

    growth_chart_data: list[dict] = []
    prev_avg_score: float | None = None
    for d in sorted(daily_group):
        b = daily_group[d]
        attempts_count = int(b["attempts"])
        completed_count = int(b["completed"])
        avg_score = (
            (b["sum_score_weighted"] / b["score_weight"])
            if b["score_weight"] > 0
            else None
        )
        completion_rate = (
            (completed_count / attempts_count) * 100 if attempts_count > 0 else None
        )
        first_pass_rate = (
            (float(b["passed"]) / completed_count) * 100
            if completed_count > 0
            else None
        )
        session_efficiency = None
        if avg_score is not None and attempts_count > 0 and b["time_seconds"] > 0:
            minutes_per_attempt = (b["time_seconds"] / attempts_count) / 60.0
            if minutes_per_attempt > 0:
                session_efficiency = avg_score / minutes_per_attempt
        stagnation_rate = None
        if avg_score is not None and prev_avg_score is not None:
            stagnation_rate = 100.0 if avg_score <= prev_avg_score else 0.0
        if avg_score is not None:
            prev_avg_score = avg_score

        growth_chart_data.append(
            {
                "date": _iso(d),
                "average_score": _round2(avg_score),
                "completion_rate": _round2(completion_rate),
                "first_attempt_pass_rate": _round2(first_pass_rate),
                "session_efficiency": _round2(session_efficiency),
                "stagnation_rate": _round2(stagnation_rate),
            }
        )

    avg_series = [
        p["average_score"] for p in growth_chart_data if p["average_score"] is not None
    ]
    last7 = avg_series[-7:]
    prev7 = avg_series[-14:-7]
    window_averages = {
        "average_score": {
            "n": len(last7),
            "last": _round2(mean(last7)) if last7 else None,
            "prev": _round2(mean(prev7)) if prev7 else None,
        }
    }
    growth_data = {
        "chart_data": growth_chart_data,
        "available_metrics": [
            {
                "id": "averageScore",
                "name": "Average Score",
                "color": "#0ea5e9",
                "unit": "%",
                "description": "Average percent score",
                "formatter_id": "percent",
            },
            {
                "id": "completionRate",
                "name": "Completion Rate",
                "color": "#22c55e",
                "unit": "%",
                "description": "Completed attempts over total attempts",
                "formatter_id": "percent",
            },
            {
                "id": "firstAttemptPassRate",
                "name": "First Pass Rate",
                "color": "#f59e0b",
                "unit": "%",
                "description": "Passes over completed attempts",
                "formatter_id": "percent",
            },
            {
                "id": "sessionEfficiency",
                "name": "Session Efficiency",
                "color": "#6366f1",
                "unit": "score/min",
                "description": "Score per minute",
                "formatter_id": "int",
            },
            {
                "id": "stagnationRate",
                "name": "Stagnation Rate",
                "color": "#ef4444",
                "unit": "%",
                "description": "Share of non-improving periods",
                "formatter_id": "percent",
            },
        ],
        "window_averages": window_averages,
        "status": _section_status(bool(growth_chart_data)),
    }

    # Persona performance
    persona_name_map = persona_name_map or {}
    persona_rows: dict[str, dict] = defaultdict(
        lambda: {
            "scores": [],
            "sessions": 0,
            "simulation_ids": set(),
            "by_date": defaultdict(list),
        }
    )
    for row in chat_rows:
        if row.persona_id is None or row.grade_percent is None:
            continue
        pid = str(row.persona_id)
        persona_rows[pid]["scores"].append(float(row.grade_percent))
        persona_rows[pid]["sessions"] += 1
        persona_rows[pid]["simulation_ids"].add(str(row.simulation_id))
        persona_rows[pid]["by_date"][row.chat_created_at.date()].append(
            float(row.grade_percent)
        )

    def persona_color(seed: str) -> str:
        h = abs(hash(seed)) % 360
        return f"hsl({h} 70% 45%)"

    persona_chart_data = []
    persona_color_junction = []
    valid_simulation_ids: set[str] = set()
    for pid, data in sorted(persona_rows.items()):
        trend = []
        for d, vals in sorted(data["by_date"].items()):
            trend.append(
                {
                    "date": _iso(d),
                    "score": _round2(mean(vals)),
                    "timestamp": d.toordinal(),
                    "simulation_id": next(iter(data["simulation_ids"]))
                    if data["simulation_ids"]
                    else None,
                }
            )
        sim_ids = sorted(data["simulation_ids"])
        valid_simulation_ids.update(sim_ids)
        color = persona_color(pid)
        persona_name = persona_name_map.get(pid, pid)
        persona_chart_data.append(
            {
                "name": persona_name,
                "score": _round2(mean(data["scores"])) if data["scores"] else None,
                "sessions": data["sessions"],
                "color": color,
                "trend_data": trend,
                "simulation_ids": sim_ids,
                "status": "neutral",
            }
        )
        persona_color_junction.append({"persona_name": persona_name, "color": color})

    persona_performance = {
        "chart_data": persona_chart_data,
        "valid_simulation_ids": sorted(valid_simulation_ids),
        "persona_colors_junction": persona_color_junction,
        "status": _section_status(bool(persona_chart_data)),
    }

    # Rubric heatmap correlation matrix from per-chat standard-group percentages
    by_rubric_chat_group: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    group_meta: dict[tuple[str, str], dict[str, str | None]] = {}
    for row in rubric_group_scores:
        if row.score_percent is None:
            continue
        rid = str(row.rubric_id)
        cid = str(row.chat_id)
        gid = str(row.standard_group_id)
        by_rubric_chat_group[rid][cid][gid] = float(row.score_percent)
        group_meta[(rid, gid)] = {
            "name": row.group_name,
            "short_name": row.group_short_name,
        }

    def _pearson(xs: list[float], ys: list[float]) -> float | None:
        if len(xs) < 3 or len(ys) < 3 or len(xs) != len(ys):
            return None
        mx = mean(xs)
        my = mean(ys)
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=False))
        den_x = sum((x - mx) ** 2 for x in xs) ** 0.5
        den_y = sum((y - my) ** 2 for y in ys) ** 0.5
        den = den_x * den_y
        if den == 0:
            return None
        return num / den

    matrices = []
    avg_abs_corrs: list[float] = []
    for rid, chat_map in sorted(by_rubric_chat_group.items()):
        group_ids = sorted(
            {gid for per_group in chat_map.values() for gid in per_group.keys()}
        )
        standard_groups = [
            {
                "id": gid,
                "name": group_meta.get((rid, gid), {}).get("name") or gid,
                "short_name": group_meta.get((rid, gid), {}).get("short_name"),
                "rubric_id": rid,
            }
            for gid in group_ids
        ]

        matrix_rows = []
        best_pair: tuple[str, str, float, int] | None = None
        has_data = False
        for g1 in group_ids:
            cells = []
            for g2 in group_ids:
                pairs = [
                    (groups[g1], groups[g2])
                    for groups in chat_map.values()
                    if g1 in groups and g2 in groups
                ]
                n = len(pairs)
                r = _pearson([p[0] for p in pairs], [p[1] for p in pairs])
                corr = r if r is not None else 0.0
                if n >= 3:
                    has_data = True
                abs_corr = abs(corr)
                if g1 != g2 and n >= 3:
                    avg_abs_corrs.append(abs_corr)
                    if best_pair is None or abs_corr > abs(best_pair[2]):
                        best_pair = (g1, g2, corr, n)
                strength = (
                    "Strong"
                    if abs_corr >= 0.7
                    else "Moderate"
                    if abs_corr >= 0.4
                    else "Weak"
                    if abs_corr > 0
                    else "No Data"
                )
                if n < 3:
                    color = "#e5e7eb"
                    strength = "No Data"
                elif corr >= 0:
                    color = (
                        "#10b981"
                        if abs_corr >= 0.7
                        else "#34d399"
                        if abs_corr >= 0.4
                        else "#a7f3d0"
                    )
                else:
                    color = (
                        "#ef4444"
                        if abs_corr >= 0.7
                        else "#f87171"
                        if abs_corr >= 0.4
                        else "#fecaca"
                    )
                cells.append(
                    {
                        "rubric_id": rid,
                        "correlation": _round2(corr),
                        "p_value": None,
                        "color": color,
                        "strength": strength,
                        "data_points": n,
                    }
                )
            matrix_rows.append({"cells": cells})

        insights = None
        if best_pair is not None:
            g1, g2, r, n = best_pair
            g1_name = group_meta.get((rid, g1), {}).get("name") or g1
            g2_name = group_meta.get((rid, g2), {}).get("name") or g2
            insights = f'Top pair: "{g1_name}" vs "{g2_name}" r={r:.2f} (n={n})'

        matrices.append(
            {
                "rubric_id": rid,
                "standard_groups": standard_groups,
                "matrix": matrix_rows,
                "insights": insights,
                "has_data": has_data,
            }
        )

    heatmap_avg = mean(avg_abs_corrs) * 100 if avg_abs_corrs else None
    if heatmap_avg is None:
        heatmap_status = "neutral"
    elif heatmap_avg >= success_threshold:
        heatmap_status = "success"
    elif heatmap_avg >= warning_threshold:
        heatmap_status = "warning"
    else:
        heatmap_status = "danger"

    rubric_heatmap = {
        "matrices": matrices,
        "valid_rubric_ids": [m["rubric_id"] for m in matrices],
        "status": heatmap_status,
    }

    return DashboardPrimaryMetrics(
        growth_data=growth_data,
        persona_performance=persona_performance,
        rubric_heatmap=rubric_heatmap,
    )


def compute_secondary_metrics(
    attempts: list[AttemptFactsItem],
    daily_rows: list[DailyMetricsItem],
    chat_rows: list[ChatFactsItem],
    profile_rows: list[ProfileMetricsItem],
    cohort_name_map: dict[str, str] | None = None,
    rubric_group_scores: list[RubricGroupScoreItem] | None = None,
    thresholds: dict[str, int] | None = None,
) -> DashboardSecondaryMetrics:
    """Compute secondary section metrics for dashboard get bundle."""
    _ = profile_rows
    success_threshold, warning_threshold, _danger_threshold = _thresholds(thresholds)
    cohort_name_map = cohort_name_map or {}

    # Cohort performance
    cohort_acc: dict[str, dict] = defaultdict(
        lambda: {
            "attempts": 0,
            "completed": 0,
            "passed": 0,
            "sum_score_weighted": 0.0,
            "score_weight": 0,
            "max_students": 0,
            "simulation_ids": set(),
        }
    )
    cohort_daily = []
    simulation_facts_map: dict[tuple[str, str], dict] = defaultdict(
        lambda: {
            "attempts": 0,
            "completed": 0,
            "passed": 0,
            "sum_score_weighted": 0.0,
            "score_weight": 0,
        }
    )
    daily_facts_map: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"attempts": 0, "sum_score_weighted": 0.0, "score_weight": 0}
    )
    valid_sim_ids: set[str] = set()

    for row in daily_rows:
        sim_id = str(row.simulation_id)
        valid_sim_ids.add(sim_id)
        day = _iso(row.date_key)

        daily_facts_key = (day, sim_id)
        daily_facts_map[daily_facts_key]["attempts"] += row.attempt_count or 0
        if row.avg_score is not None and (row.attempt_count or 0) > 0:
            daily_facts_map[daily_facts_key]["sum_score_weighted"] += float(
                row.avg_score
            ) * float(row.attempt_count)
            daily_facts_map[daily_facts_key]["score_weight"] += row.attempt_count

        if row.cohort_id is None:
            continue
        cohort_id = str(row.cohort_id)
        c = cohort_acc[cohort_id]
        c["attempts"] += row.attempt_count or 0
        c["completed"] += row.completed_count or 0
        c["passed"] += row.passed_count or 0
        c["max_students"] = max(c["max_students"], row.unique_profiles or 0)
        c["simulation_ids"].add(sim_id)
        if row.avg_score is not None and (row.attempt_count or 0) > 0:
            c["sum_score_weighted"] += float(row.avg_score) * float(row.attempt_count)
            c["score_weight"] += row.attempt_count

        cohort_daily.append(
            {"date": day, "avg_score": _round2(row.avg_score), "cohort_id": cohort_id}
        )

        k = (cohort_id, sim_id)
        simulation_facts_map[k]["attempts"] += row.attempt_count or 0
        simulation_facts_map[k]["completed"] += row.completed_count or 0
        simulation_facts_map[k]["passed"] += row.passed_count or 0
        if row.avg_score is not None and (row.attempt_count or 0) > 0:
            simulation_facts_map[k]["sum_score_weighted"] += float(
                row.avg_score
            ) * float(row.attempt_count)
            simulation_facts_map[k]["score_weight"] += row.attempt_count

    cohort_data = []
    for cohort_id, c in sorted(cohort_acc.items()):
        attempts_count = c["attempts"]
        completed_count = c["completed"]
        passed_count = c["passed"]
        pass_rate = (passed_count / completed_count * 100) if completed_count > 0 else 0
        avg_score = (
            c["sum_score_weighted"] / c["score_weight"] if c["score_weight"] > 0 else 0
        )
        cohort_data.append(
            {
                "id": cohort_id,
                "name": cohort_name_map.get(cohort_id, cohort_id),
                "pass_rate": _round2(pass_rate),
                "avg_percentage_score": _round2(avg_score),
                "total_students": c["max_students"],
                "passed_students": None,
                "total_attempts": attempts_count,
                "passed_attempts": passed_count,
                "simulation_count": len(c["simulation_ids"]),
                "required_simulations": len(c["simulation_ids"]),
                "status": "neutral",
            }
        )

    simulation_facts = []
    for (cohort_id, sim_id), c in sorted(simulation_facts_map.items()):
        pass_rate = (c["passed"] / c["completed"] * 100) if c["completed"] > 0 else 0
        avg_score = (
            c["sum_score_weighted"] / c["score_weight"] if c["score_weight"] > 0 else 0
        )
        simulation_facts.append(
            {
                "cohort_id": cohort_id,
                "simulation_id": sim_id,
                "pass_rate": _round2(pass_rate),
                "avg_score": _round2(avg_score),
                "attempts": c["attempts"],
            }
        )

    daily_facts = []
    for (day, sim_id), c in sorted(daily_facts_map.items()):
        avg_score = (
            c["sum_score_weighted"] / c["score_weight"] if c["score_weight"] > 0 else 0
        )
        daily_facts.append(
            {"date": day, "simulation_id": sim_id, "avg_score": _round2(avg_score)}
        )

    cohort_avg = (
        mean(
            [
                c["avg_percentage_score"]
                for c in cohort_data
                if c["avg_percentage_score"] is not None
            ]
        )
        if cohort_data
        else None
    )
    cohort_status = (
        "neutral"
        if cohort_avg is None
        else "success"
        if cohort_avg >= success_threshold
        else "warning"
        if cohort_avg >= warning_threshold
        else "danger"
    )
    cohort_performance = {
        "cohort_data": cohort_data,
        "daily_data": cohort_daily,
        "simulation_facts": simulation_facts,
        "daily_facts": daily_facts,
        "valid_simulation_ids": sorted(valid_sim_ids),
        "status": cohort_status,
    }

    # Attempt improvement
    attempts_by_profile: dict[str, list[AttemptFactsItem]] = defaultdict(list)
    for item in attempts:
        if item.profile_id is None or item.attempt_created_at is None:
            continue
        attempts_by_profile[str(item.profile_id)].append(item)

    attempt_fact_acc: dict[tuple[str, int], dict] = defaultdict(
        lambda: {"count": 0, "sum_grade": 0.0, "sum_minutes": 0.0, "passed": 0}
    )
    attempt_chart_acc: dict[int, dict] = defaultdict(
        lambda: {"count": 0, "sum_grade": 0.0, "sum_minutes": 0.0, "passed": 0}
    )
    attempt_valid_sim_ids: set[str] = set()

    for items in attempts_by_profile.values():
        for idx, item in enumerate(
            sorted(items, key=lambda a: a.attempt_created_at), start=1
        ):
            if item.simulation_id is None:
                continue
            sim_id = str(item.simulation_id)
            attempt_valid_sim_ids.add(sim_id)
            grade = float(item.score_percent) if item.score_percent is not None else 0.0
            minutes = float(item.total_time_seconds or 0) / 60.0
            passed = 1 if item.has_passed else 0

            k = (sim_id, idx)
            attempt_fact_acc[k]["count"] += 1
            attempt_fact_acc[k]["sum_grade"] += grade
            attempt_fact_acc[k]["sum_minutes"] += minutes
            attempt_fact_acc[k]["passed"] += passed

            attempt_chart_acc[idx]["count"] += 1
            attempt_chart_acc[idx]["sum_grade"] += grade
            attempt_chart_acc[idx]["sum_minutes"] += minutes
            attempt_chart_acc[idx]["passed"] += passed

    attempt_facts = []
    for (sim_id, attempt_no), d in sorted(
        attempt_fact_acc.items(), key=lambda x: (x[0][1], x[0][0])
    ):
        cnt = d["count"]
        attempt_facts.append(
            {
                "simulation_id": sim_id,
                "attempt_no": attempt_no,
                "avg_grade": _round2(d["sum_grade"] / cnt if cnt else 0),
                "avg_minutes": _round2(d["sum_minutes"] / cnt if cnt else 0),
                "pass_rate": _round2((d["passed"] / cnt * 100) if cnt else 0),
            }
        )

    attempt_chart_data = []
    for attempt_no, d in sorted(attempt_chart_acc.items()):
        cnt = d["count"]
        attempt_chart_data.append(
            {
                "attempt": f"Attempt {attempt_no}",
                "average_score": _round2(d["sum_grade"] / cnt if cnt else 0),
                "average_time": _round2(d["sum_minutes"] / cnt if cnt else 0),
                "pass_rate": _round2((d["passed"] / cnt * 100) if cnt else 0),
            }
        )

    attempt_avg = (
        mean(
            [
                c["average_score"]
                for c in attempt_chart_data
                if c["average_score"] is not None
            ]
        )
        if attempt_chart_data
        else None
    )
    attempt_status = (
        "neutral"
        if attempt_avg is None
        else "success"
        if attempt_avg >= success_threshold
        else "warning"
        if attempt_avg >= warning_threshold
        else "danger"
    )
    attempt_improvement = {
        "chart_data": attempt_chart_data,
        "facts": attempt_facts,
        "valid_simulation_ids": sorted(attempt_valid_sim_ids),
        "status": attempt_status,
    }

    # Skill performance (per-standard-group radar from rubric_group_scores)
    rubric_group_scores = rubric_group_scores or []

    # Aggregate scores per rubric × standard group
    group_scores: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    group_info: dict[tuple[str, str], dict] = {}
    for row in rubric_group_scores:
        if row.score_percent is None:
            continue
        rid = str(row.rubric_id)
        gid = str(row.standard_group_id)
        group_scores[rid][gid].append(float(row.score_percent))
        group_info[(rid, gid)] = {
            "name": row.group_name,
            "short_name": row.group_short_name,
        }

    # Also collect per-rubric × simulation group_facts for the detail table
    rubric_sim_group: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for row in rubric_group_scores:
        if row.score_percent is None or row.chat_id is None:
            continue
        rid = str(row.rubric_id)
        gid = str(row.standard_group_id)
        # Map chat_id back to simulation_id via chat_rows lookup
        rubric_sim_group[(rid, gid, "all")].append(float(row.score_percent))

    skill_packages = []
    valid_rubrics = sorted(group_scores.keys())
    for rid in valid_rubrics:
        radar_data = []
        for gid, scores in sorted(group_scores[rid].items()):
            avg_pct = mean(scores) if scores else 0.0
            info = group_info.get((rid, gid), {})
            radar_data.append(
                {
                    "metric": info.get("short_name") or info.get("name") or gid,
                    "description": info.get("name"),
                    "value": _round2(avg_pct / 100.0),
                    "full_mark": 1.0,
                }
            )

        group_facts = []
        for gid, scores in sorted(group_scores[rid].items()):
            avg_pct = mean(scores) if scores else 0.0
            info = group_info.get((rid, gid), {})
            group_facts.append(
                {
                    "group_id": gid,
                    "group_name": info.get("name") or gid,
                    "group_description": None,
                    "simulation_id": None,
                    "score": _round2(avg_pct),
                    "points": _round2(100.0),
                    "avg_pct": _round2(avg_pct),
                }
            )

        skill_packages.append(
            {
                "rubric_id": rid,
                "radar_data": radar_data,
                "group_facts": group_facts,
            }
        )

    skill_avg = (
        mean(
            [
                r["value"]
                for p in skill_packages
                for r in p["radar_data"]
                if r["value"] is not None
            ]
        )
        if skill_packages
        else None
    )
    skill_avg_pct = skill_avg * 100.0 if skill_avg is not None else None
    skill_status = (
        "neutral"
        if skill_avg_pct is None
        else "success"
        if skill_avg_pct >= success_threshold
        else "warning"
        if skill_avg_pct >= warning_threshold
        else "danger"
    )
    skill_performance = {
        "packages": skill_packages,
        "valid_rubric_ids": valid_rubrics,
        "status": skill_status,
    }

    return DashboardSecondaryMetrics(
        cohort_performance=cohort_performance,
        attempt_improvement=attempt_improvement,
        skill_performance=skill_performance,
    )


def compute_footer_metrics(
    attempts: list[AttemptFactsItem],
    daily_rows: list[DailyMetricsItem],
    chat_rows: list[ChatFactsItem],
    profile_rows: list[ProfileMetricsItem],
    parameter_fields: list[Any] | None = None,
    parameters: list[Any] | None = None,
    fields: list[Any] | None = None,
    simulation_name_map: dict[str, str] | None = None,
    scenario_name_map: dict[str, str] | None = None,
    thresholds: dict[str, int] | None = None,
) -> DashboardFooterMetrics:
    """Compute footer section metrics for dashboard get bundle."""
    _ = (daily_rows, profile_rows)
    success_threshold, warning_threshold, _danger_threshold = _thresholds(thresholds)
    simulation_name_map = simulation_name_map or {}
    scenario_name_map = scenario_name_map or {}

    parameter_fields = parameter_fields or []
    parameters = parameters or []
    fields = fields or []

    pf_lookup: dict[str, tuple[str, str]] = {}
    for pf in parameter_fields:
        pf_id = getattr(pf, "id", None)
        pid = getattr(pf, "parameter_id", None)
        fid = getattr(pf, "field_id", None)
        if pf_id and pid and fid:
            pf_lookup[str(pf_id)] = (str(pid), str(fid))

    field_name_by_id: dict[str, str] = {}
    for f in fields:
        field_id = getattr(f, "field_id", None)
        name = getattr(f, "name", None)
        if field_id and name:
            field_name_by_id[str(field_id)] = str(name)

    persona_doc_parameter_ids: set[str] = set()
    for p in parameters:
        pid = getattr(p, "parameter_id", None)
        if not pid:
            continue
        if bool(getattr(p, "document_parameter", False)) or bool(
            getattr(p, "persona_parameter", False)
        ):
            persona_doc_parameter_ids.add(str(pid))

    scenario_to_param_items: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in chat_rows:
        scenario_id = str(row.scenario_id)
        if row.parameter_field_ids:
            for pfid in row.parameter_field_ids:
                pair = pf_lookup.get(str(pfid))
                if pair:
                    scenario_to_param_items[scenario_id].add(pair)
        elif row.parameter_ids and row.field_ids:
            for pid in row.parameter_ids:
                for fid in row.field_ids:
                    scenario_to_param_items[scenario_id].add((str(pid), str(fid)))
        if row.persona_parameter_field_ids:
            for pfid in row.persona_parameter_field_ids:
                pair = pf_lookup.get(str(pfid))
                if pair:
                    scenario_to_param_items[scenario_id].add(pair)
        if row.document_parameter_field_ids:
            for pfid in row.document_parameter_field_ids:
                pair = pf_lookup.get(str(pfid))
                if pair:
                    scenario_to_param_items[scenario_id].add(pair)

    valid_parameter_ids = sorted(
        {
            pid
            for pairs in scenario_to_param_items.values()
            for (pid, _fid) in pairs
            if pid not in persona_doc_parameter_ids
        }
    )

    # Scenario simulation performance — group by (sim_id, scenario_id)
    scenario_acc: dict[tuple[str, str], dict] = defaultdict(
        lambda: {
            "count": 0,
            "completed": 0,
            "passed": 0,
            "sum_score": 0.0,
            "score_count": 0,
        }
    )
    valid_scenario_ids: set[str] = set()
    for row in chat_rows:
        sim_id = str(row.simulation_id)
        scenario_id = str(row.scenario_id)
        valid_scenario_ids.add(scenario_id)
        k = (sim_id, scenario_id)
        scenario_acc[k]["count"] += 1
        scenario_acc[k]["completed"] += 1 if row.completed else 0
        scenario_acc[k]["passed"] += 1 if row.passed else 0
        if row.grade_percent is not None:
            scenario_acc[k]["sum_score"] += float(row.grade_percent)
            scenario_acc[k]["score_count"] += 1

    sim_perf_facts = []
    for (sim_id, scenario_id), d in sorted(scenario_acc.items()):
        sim_perf_facts.append(
            {
                "scenario_id": scenario_id,
                "simulation_id": sim_id,
                "simulation_name": simulation_name_map.get(sim_id, sim_id),
                "avg_score": _round2(
                    d["sum_score"] / d["score_count"] if d["score_count"] else 0
                ),
                "success_rate": _round2(
                    (d["passed"] / d["completed"] * 100) if d["completed"] else 0
                ),
                "total_attempts": d["count"],
                "completed_attempts": d["completed"],
            }
        )

    perf_score = (
        mean(
            [
                (0.7 * (f["avg_score"] or 0)) + (0.3 * (f["success_rate"] or 0))
                for f in sim_perf_facts
            ]
        )
        if sim_perf_facts
        else None
    )
    perf_status = (
        "neutral"
        if perf_score is None
        else "success"
        if perf_score >= success_threshold
        else "warning"
        if perf_score >= warning_threshold
        else "danger"
    )
    scenario_simulation_performance = {
        "simulation_facts": sim_perf_facts,
        "valid_scenario_ids": sorted(valid_scenario_ids),
        "status": perf_status,
    }

    # Scenario composition — split chats within each scenario into high/low by score
    # Step 1: collect chat scores per scenario
    scenario_chat_scores: dict[str, list[float]] = defaultdict(list)
    for row in chat_rows:
        scenario_id = str(row.scenario_id)
        if row.grade_percent is not None:
            scenario_chat_scores[scenario_id].append(float(row.grade_percent))

    # Step 2: compute median threshold per scenario
    scenario_median: dict[str, float] = {}
    for scenario_id, scores in scenario_chat_scores.items():
        if scores:
            sorted_scores = sorted(scores)
            mid = len(sorted_scores) // 2
            if len(sorted_scores) % 2 == 0:
                scenario_median[scenario_id] = (
                    sorted_scores[mid - 1] + sorted_scores[mid]
                ) / 2
            else:
                scenario_median[scenario_id] = sorted_scores[mid]

    # Step 3: classify each chat and count parameters per (scenario, group)
    scenario_group_stats: dict[str, dict[str, dict]] = defaultdict(
        lambda: {
            "high": {"count": 0, "sum_score": 0.0, "score_count": 0},
            "low": {"count": 0, "sum_score": 0.0, "score_count": 0},
        }
    )
    param_group_counts: dict[tuple[str, str, str, str], int] = defaultdict(int)
    for row in chat_rows:
        scenario_id = str(row.scenario_id)
        median = scenario_median.get(scenario_id)
        if median is None or row.grade_percent is None:
            continue
        group = "high" if float(row.grade_percent) >= median else "low"
        g = scenario_group_stats[scenario_id][group]
        g["count"] += 1
        g["sum_score"] += float(row.grade_percent)
        g["score_count"] += 1
        for pid in row.parameter_ids or []:
            pid_str = str(pid)
            field_id = str(row.field_ids[0]) if row.field_ids else ""
            param_group_counts[(scenario_id, group, pid_str, field_id)] += 1

    # Step 4: build summaries and parameter facts
    scenario_summaries = []
    for scenario_id in sorted(scenario_group_stats.keys()):
        h = scenario_group_stats[scenario_id]["high"]
        lo = scenario_group_stats[scenario_id]["low"]
        scenario_summaries.append(
            {
                "scenario_id": scenario_id,
                "name": scenario_name_map.get(scenario_id, scenario_id),
                "total_chats": h["count"] + lo["count"],
                "high_count": h["count"],
                "low_count": lo["count"],
                "high_avg_score": _round2(
                    h["sum_score"] / h["score_count"] if h["score_count"] else 0
                ),
                "low_avg_score": _round2(
                    lo["sum_score"] / lo["score_count"] if lo["score_count"] else 0
                ),
            }
        )

    chat_parameter_facts = []
    for (scenario_id, group, pid, field_id), count in sorted(
        param_group_counts.items()
    ):
        chat_parameter_facts.append(
            {
                "scenario_id": scenario_id,
                "group": group,
                "parameter_id": pid,
                "parameter_item_id": field_id or None,
                "chat_count": count,
            }
        )

    comp_status = "success" if scenario_summaries else "neutral"
    scenario_composition = {
        "scenario_summaries": scenario_summaries,
        "chat_parameter_facts": chat_parameter_facts,
        "valid_scenario_ids": sorted(valid_scenario_ids),
        "status": comp_status,
    }

    # Scenario performance categorical facts (scenario parameters only, not persona/document)
    cat_map_seen = [
        (pid, fid, scenario_id)
        for scenario_id, pairs in scenario_to_param_items.items()
        for (pid, fid) in sorted(pairs)
        if pid not in persona_doc_parameter_ids
    ]
    attempt_daily: dict[tuple[str, str, str], dict] = defaultdict(
        lambda: {"scores": [], "attempts": 0, "passed_attempts": 0}
    )
    for row in chat_rows:
        if row.grade_percent is None:
            continue
        day = _iso(row.attempt_created_at.date())
        scenario_id = str(row.scenario_id)
        for pid, fid in scenario_to_param_items.get(scenario_id, set()):
            if pid in persona_doc_parameter_ids:
                continue
            k = (pid, fid, day)
            attempt_daily[k]["scores"].append(float(row.grade_percent))
            attempt_daily[k]["attempts"] += 1
            attempt_daily[k]["passed_attempts"] += 1 if row.passed else 0

    attribute_attempt_facts = []
    for (pid, fid, day), d in sorted(attempt_daily.items()):
        attribute_attempt_facts.append(
            {
                "parameter_id": pid,
                "parameter_item_id": fid,
                "date": day,
                "timestamp": None,
                "avg_score": _round2(mean(d["scores"])) if d["scores"] else None,
                "attempts": d["attempts"],
                "passed_attempts": d["passed_attempts"],
            }
        )

    attribute_scenario_facts = [
        {"parameter_id": pid, "parameter_item_id": fid, "scenario_id": scenario_id}
        for (pid, fid, scenario_id) in cat_map_seen
    ]

    cat_avg = (
        mean(
            [
                f["avg_score"]
                for f in attribute_attempt_facts
                if f["avg_score"] is not None
            ]
        )
        if attribute_attempt_facts
        else None
    )
    if cat_avg is None:
        scenario_perf_status = "neutral"
    elif cat_avg >= success_threshold:
        scenario_perf_status = "success"
    elif cat_avg >= warning_threshold:
        scenario_perf_status = "warning"
    else:
        scenario_perf_status = "danger"

    scenario_performance = {
        "attribute_attempt_facts": attribute_attempt_facts,
        "attribute_scenario_facts": attribute_scenario_facts,
        "valid_parameter_ids": valid_parameter_ids,
        "status": scenario_perf_status,
    }

    # Scenario stats numeric level facts (document/persona parameters)
    param_levels: dict[str, list[str]] = defaultdict(list)
    for pairs in scenario_to_param_items.values():
        for pid, fid in pairs:
            if pid in persona_doc_parameter_ids and fid not in param_levels[pid]:
                param_levels[pid].append(fid)
    for pid in param_levels:
        param_levels[pid].sort()

    scenario_numeric_map: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    for scenario_id, pairs in scenario_to_param_items.items():
        for pid, fid in pairs:
            if pid not in persona_doc_parameter_ids:
                continue
            level = param_levels[pid].index(fid) + 1 if fid in param_levels[pid] else 1
            scenario_numeric_map[scenario_id].append((pid, level, fid))

    numeric_acc: dict[tuple[str, str, float], dict] = defaultdict(
        lambda: {"scores": [], "attempts": 0}
    )
    for row in chat_rows:
        if row.grade_percent is None:
            continue
        for pid, level, fid in scenario_numeric_map.get(str(row.scenario_id), []):
            label = field_name_by_id.get(fid, str(level))
            k = (pid, label, float(level))
            numeric_acc[k]["scores"].append(float(row.grade_percent))
            numeric_acc[k]["attempts"] += 1

    numeric_attempt_facts = []
    for (pid, label, level), d in sorted(
        numeric_acc.items(), key=lambda x: (x[0][0], x[0][2])
    ):
        numeric_attempt_facts.append(
            {
                "parameter_id": pid,
                "level_label": label,
                "level_value": _round2(level),
                "score": _round2(mean(d["scores"])) if d["scores"] else None,
                "attempts": d["attempts"],
            }
        )

    numeric_scenario_facts = []
    for scenario_id, vals in sorted(scenario_numeric_map.items()):
        for pid, level, fid in sorted(vals, key=lambda x: (x[0], x[1])):
            numeric_scenario_facts.append(
                {
                    "parameter_id": pid,
                    "scenario_id": scenario_id,
                    "level_label": field_name_by_id.get(fid, str(level)),
                    "level_value": _round2(float(level)),
                }
            )

    valid_persona_doc_parameter_ids = sorted(
        {f["parameter_id"] for f in numeric_attempt_facts}
    )
    num_avg = (
        mean([f["score"] for f in numeric_attempt_facts if f["score"] is not None])
        if numeric_attempt_facts
        else None
    )
    if num_avg is None:
        scenario_stats_status = "neutral"
    elif num_avg >= success_threshold:
        scenario_stats_status = "success"
    elif num_avg >= warning_threshold:
        scenario_stats_status = "warning"
    else:
        scenario_stats_status = "danger"

    scenario_stats = {
        "numeric_attempt_facts": numeric_attempt_facts,
        "numeric_scenario_facts": numeric_scenario_facts,
        "valid_numeric_parameter_ids": valid_persona_doc_parameter_ids,
        "status": scenario_stats_status,
    }

    return DashboardFooterMetrics(
        scenario_performance=scenario_performance,
        scenario_stats=scenario_stats,
        scenario_simulation_performance=scenario_simulation_performance,
        scenario_composition=scenario_composition,
    )


def compute_footer_metrics_v2(
    scenario_facts_items: list[ScenarioFactsItem],
    scenarios: list[Any],
    personas: list[Any],
    documents: list[Any],
    parameter_fields: list[Any] | None = None,
    parameters: list[Any] | None = None,
    fields: list[Any] | None = None,
    simulation_name_map: dict[str, str] | None = None,
    scenario_name_map: dict[str, str] | None = None,
    thresholds: dict[str, int] | None = None,
) -> DashboardFooterMetrics:
    """Compute footer metrics from mv_scenario_facts + hydrated resources.

    Resolves parameter_field_ids at runtime from hydrated scenario/persona/document
    resources instead of from denormalized chat_rows fields.
    """
    success_threshold, warning_threshold, _danger_threshold = _thresholds(thresholds)
    simulation_name_map = simulation_name_map or {}
    scenario_name_map = scenario_name_map or {}

    parameter_fields = parameter_fields or []
    parameters = parameters or []
    fields = fields or []

    # --- Build lookups (same as v1) ---
    pf_lookup: dict[str, tuple[str, str]] = {}
    for pf in parameter_fields:
        pf_id = getattr(pf, "id", None)
        pid = getattr(pf, "parameter_id", None)
        fid = getattr(pf, "field_id", None)
        if pf_id and pid and fid:
            pf_lookup[str(pf_id)] = (str(pid), str(fid))

    field_name_by_id: dict[str, str] = {}
    for f in fields:
        field_id = getattr(f, "field_id", None)
        name = getattr(f, "name", None)
        if field_id and name:
            field_name_by_id[str(field_id)] = str(name)

    persona_doc_parameter_ids: set[str] = set()
    for p in parameters:
        pid = getattr(p, "parameter_id", None)
        if not pid:
            continue
        if bool(getattr(p, "document_parameter", False)) or bool(
            getattr(p, "persona_parameter", False)
        ):
            persona_doc_parameter_ids.add(str(pid))

    # --- Build scenario_to_param_items from hydrated resources ---
    # Scenario → persona mapping from scenario resources
    scenario_persona_map: dict[str, set[str]] = {}
    for s in scenarios:
        sid = str(getattr(s, "scenario_id", None))
        p_ids = getattr(s, "persona_ids", None) or []
        scenario_persona_map[sid] = {str(pid) for pid in p_ids}

    # Scenario → document mapping from scenario_facts rows
    scenario_document_map: dict[str, set[str]] = defaultdict(set)
    for row in scenario_facts_items:
        if row.scenario_id:
            for doc_id in row.document_ids or []:
                scenario_document_map[str(row.scenario_id)].add(str(doc_id))

    scenario_to_param_items: dict[str, set[tuple[str, str]]] = defaultdict(set)

    # From scenario resource parameter_field_ids
    for s in scenarios:
        sid = str(getattr(s, "scenario_id", None))
        for pfid in getattr(s, "parameter_field_ids", None) or []:
            pair = pf_lookup.get(str(pfid))
            if pair:
                scenario_to_param_items[sid].add(pair)

    # From persona resource parameter_field_ids → add to scenarios that use this persona
    for p in personas:
        pid = str(getattr(p, "persona_id", None))
        pf_ids = getattr(p, "parameter_field_ids", None) or []
        if not pf_ids:
            continue
        for sid, persona_set in scenario_persona_map.items():
            if pid in persona_set:
                for pfid in pf_ids:
                    pair = pf_lookup.get(str(pfid))
                    if pair:
                        scenario_to_param_items[sid].add(pair)

    # From document resource parameter_field_ids → add to scenarios that use this document
    for d in documents:
        did = str(getattr(d, "document_id", None))
        pf_ids = getattr(d, "parameter_field_ids", None) or []
        if not pf_ids:
            continue
        for sid, doc_set in scenario_document_map.items():
            if did in doc_set:
                for pfid in pf_ids:
                    pair = pf_lookup.get(str(pfid))
                    if pair:
                        scenario_to_param_items[sid].add(pair)

    valid_parameter_ids = sorted(
        {
            pid
            for pairs in scenario_to_param_items.values()
            for (pid, _fid) in pairs
            if pid not in persona_doc_parameter_ids
        }
    )

    # --- 1. Scenario simulation performance — group by (sim_id, scenario_id) ---
    scenario_acc: dict[tuple[str, str], dict] = defaultdict(
        lambda: {
            "count": 0,
            "completed": 0,
            "passed": 0,
            "sum_score": 0.0,
            "score_count": 0,
        }
    )
    valid_scenario_ids_v2: set[str] = set()
    for row in scenario_facts_items:
        sim_id = str(row.simulation_id)
        scenario_id = str(row.scenario_id) if row.scenario_id else None
        if not scenario_id:
            continue
        valid_scenario_ids_v2.add(scenario_id)
        k = (sim_id, scenario_id)
        scenario_acc[k]["count"] += 1
        scenario_acc[k]["completed"] += 1 if row.completed else 0
        scenario_acc[k]["passed"] += 1 if row.passed else 0
        if row.grade_percent is not None:
            scenario_acc[k]["sum_score"] += float(row.grade_percent)
            scenario_acc[k]["score_count"] += 1

    sim_perf_facts_v2 = []
    for (sim_id, scenario_id), d in sorted(scenario_acc.items()):
        sim_perf_facts_v2.append(
            {
                "scenario_id": scenario_id,
                "simulation_id": sim_id,
                "simulation_name": simulation_name_map.get(sim_id, sim_id),
                "avg_score": _round2(
                    d["sum_score"] / d["score_count"] if d["score_count"] else 0
                ),
                "success_rate": _round2(
                    (d["passed"] / d["completed"] * 100) if d["completed"] else 0
                ),
                "total_attempts": d["count"],
                "completed_attempts": d["completed"],
            }
        )

    perf_score = (
        mean(
            [
                (0.7 * (f["avg_score"] or 0)) + (0.3 * (f["success_rate"] or 0))
                for f in sim_perf_facts_v2
            ]
        )
        if sim_perf_facts_v2
        else None
    )
    perf_status = (
        "neutral"
        if perf_score is None
        else "success"
        if perf_score >= success_threshold
        else "warning"
        if perf_score >= warning_threshold
        else "danger"
    )
    scenario_simulation_performance = {
        "simulation_facts": sim_perf_facts_v2,
        "valid_scenario_ids": sorted(valid_scenario_ids_v2),
        "status": perf_status,
    }

    # --- 2. Scenario composition — split chats within each scenario into high/low ---
    # Step 1: collect chat scores per scenario
    scenario_chat_scores_v2: dict[str, list[float]] = defaultdict(list)
    for row in scenario_facts_items:
        scenario_id = str(row.scenario_id) if row.scenario_id else None
        if not scenario_id:
            continue
        if row.grade_percent is not None:
            scenario_chat_scores_v2[scenario_id].append(float(row.grade_percent))

    # Step 2: compute median threshold per scenario
    scenario_median_v2: dict[str, float] = {}
    for scenario_id, scores in scenario_chat_scores_v2.items():
        if scores:
            sorted_scores = sorted(scores)
            mid = len(sorted_scores) // 2
            if len(sorted_scores) % 2 == 0:
                scenario_median_v2[scenario_id] = (
                    sorted_scores[mid - 1] + sorted_scores[mid]
                ) / 2
            else:
                scenario_median_v2[scenario_id] = sorted_scores[mid]

    # Step 3: classify each chat and count parameters per (scenario, group)
    scenario_group_stats_v2: dict[str, dict[str, dict]] = defaultdict(
        lambda: {
            "high": {"count": 0, "sum_score": 0.0, "score_count": 0},
            "low": {"count": 0, "sum_score": 0.0, "score_count": 0},
        }
    )
    param_group_counts_v2: dict[tuple[str, str, str, str], int] = defaultdict(int)
    for row in scenario_facts_items:
        scenario_id = str(row.scenario_id) if row.scenario_id else None
        if not scenario_id:
            continue
        median = scenario_median_v2.get(scenario_id)
        if median is None or row.grade_percent is None:
            continue
        group = "high" if float(row.grade_percent) >= median else "low"
        g = scenario_group_stats_v2[scenario_id][group]
        g["count"] += 1
        g["sum_score"] += float(row.grade_percent)
        g["score_count"] += 1
        for pid, fid in scenario_to_param_items.get(scenario_id, set()):
            param_group_counts_v2[(scenario_id, group, pid, fid)] += 1

    # Step 4: build summaries and parameter facts
    scenario_summaries_v2 = []
    for scenario_id in sorted(scenario_group_stats_v2.keys()):
        h = scenario_group_stats_v2[scenario_id]["high"]
        lo = scenario_group_stats_v2[scenario_id]["low"]
        scenario_summaries_v2.append(
            {
                "scenario_id": scenario_id,
                "name": scenario_name_map.get(scenario_id, scenario_id),
                "total_chats": h["count"] + lo["count"],
                "high_count": h["count"],
                "low_count": lo["count"],
                "high_avg_score": _round2(
                    h["sum_score"] / h["score_count"] if h["score_count"] else 0
                ),
                "low_avg_score": _round2(
                    lo["sum_score"] / lo["score_count"] if lo["score_count"] else 0
                ),
            }
        )

    chat_parameter_facts_v2: list[dict] = []
    for (scenario_id, group, pid, field_id), count in sorted(
        param_group_counts_v2.items()
    ):
        chat_parameter_facts_v2.append(
            {
                "scenario_id": scenario_id,
                "group": group,
                "parameter_id": pid,
                "parameter_item_id": field_id or None,
                "chat_count": count,
            }
        )

    comp_status = "success" if scenario_summaries_v2 else "neutral"
    scenario_composition = {
        "scenario_summaries": scenario_summaries_v2,
        "chat_parameter_facts": chat_parameter_facts_v2,
        "valid_scenario_ids": sorted(valid_scenario_ids_v2),
        "status": comp_status,
    }

    # --- 3. Scenario performance categorical facts ---
    cat_map_seen = [
        (pid, fid, scenario_id)
        for scenario_id, pairs in scenario_to_param_items.items()
        for (pid, fid) in sorted(pairs)
        if pid not in persona_doc_parameter_ids
    ]
    attempt_daily: dict[tuple[str, str, str], dict] = defaultdict(
        lambda: {"scores": [], "attempts": 0, "passed_attempts": 0}
    )
    for row in scenario_facts_items:
        if row.grade_percent is None or row.attempt_date is None:
            continue
        day = _iso(row.attempt_date)
        scenario_id = str(row.scenario_id) if row.scenario_id else None
        if not scenario_id:
            continue
        for pid, fid in scenario_to_param_items.get(scenario_id, set()):
            if pid in persona_doc_parameter_ids:
                continue
            k = (pid, fid, day)
            attempt_daily[k]["scores"].append(float(row.grade_percent))
            attempt_daily[k]["attempts"] += 1
            attempt_daily[k]["passed_attempts"] += 1 if row.passed else 0

    attribute_attempt_facts = []
    for (pid, fid, day), d in sorted(attempt_daily.items()):
        attribute_attempt_facts.append(
            {
                "parameter_id": pid,
                "parameter_item_id": fid,
                "date": day,
                "timestamp": None,
                "avg_score": _round2(mean(d["scores"])) if d["scores"] else None,
                "attempts": d["attempts"],
                "passed_attempts": d["passed_attempts"],
            }
        )

    attribute_scenario_facts = [
        {"parameter_id": pid, "parameter_item_id": fid, "scenario_id": scenario_id}
        for (pid, fid, scenario_id) in cat_map_seen
    ]

    cat_avg = (
        mean(
            [
                f["avg_score"]
                for f in attribute_attempt_facts
                if f["avg_score"] is not None
            ]
        )
        if attribute_attempt_facts
        else None
    )
    if cat_avg is None:
        scenario_perf_status = "neutral"
    elif cat_avg >= success_threshold:
        scenario_perf_status = "success"
    elif cat_avg >= warning_threshold:
        scenario_perf_status = "warning"
    else:
        scenario_perf_status = "danger"

    scenario_performance = {
        "attribute_attempt_facts": attribute_attempt_facts,
        "attribute_scenario_facts": attribute_scenario_facts,
        "valid_parameter_ids": valid_parameter_ids,
        "status": scenario_perf_status,
    }

    # --- 4. Scenario stats numeric level facts ---
    param_levels: dict[str, list[str]] = defaultdict(list)
    for pairs in scenario_to_param_items.values():
        for pid, fid in pairs:
            if pid in persona_doc_parameter_ids and fid not in param_levels[pid]:
                param_levels[pid].append(fid)
    for pid in param_levels:
        param_levels[pid].sort()

    scenario_numeric_map: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    for scenario_id, pairs in scenario_to_param_items.items():
        for pid, fid in pairs:
            if pid not in persona_doc_parameter_ids:
                continue
            level = param_levels[pid].index(fid) + 1 if fid in param_levels[pid] else 1
            scenario_numeric_map[scenario_id].append((pid, level, fid))

    numeric_acc: dict[tuple[str, str, float], dict] = defaultdict(
        lambda: {"scores": [], "attempts": 0}
    )
    for row in scenario_facts_items:
        if row.grade_percent is None:
            continue
        scenario_id = str(row.scenario_id) if row.scenario_id else None
        if not scenario_id:
            continue
        for pid, level, fid in scenario_numeric_map.get(scenario_id, []):
            label = field_name_by_id.get(fid, str(level))
            k = (pid, label, float(level))
            numeric_acc[k]["scores"].append(float(row.grade_percent))
            numeric_acc[k]["attempts"] += 1

    numeric_attempt_facts = []
    for (pid, label, level), d in sorted(
        numeric_acc.items(), key=lambda x: (x[0][0], x[0][2])
    ):
        numeric_attempt_facts.append(
            {
                "parameter_id": pid,
                "level_label": label,
                "level_value": _round2(level),
                "score": _round2(mean(d["scores"])) if d["scores"] else None,
                "attempts": d["attempts"],
            }
        )

    numeric_scenario_facts = []
    for scenario_id, vals in sorted(scenario_numeric_map.items()):
        for pid, level, fid in sorted(vals, key=lambda x: (x[0], x[1])):
            numeric_scenario_facts.append(
                {
                    "parameter_id": pid,
                    "scenario_id": scenario_id,
                    "level_label": field_name_by_id.get(fid, str(level)),
                    "level_value": _round2(float(level)),
                }
            )

    valid_persona_doc_parameter_ids = sorted(
        {f["parameter_id"] for f in numeric_attempt_facts}
    )
    num_avg = (
        mean([f["score"] for f in numeric_attempt_facts if f["score"] is not None])
        if numeric_attempt_facts
        else None
    )
    if num_avg is None:
        scenario_stats_status = "neutral"
    elif num_avg >= success_threshold:
        scenario_stats_status = "success"
    elif num_avg >= warning_threshold:
        scenario_stats_status = "warning"
    else:
        scenario_stats_status = "danger"

    scenario_stats = {
        "numeric_attempt_facts": numeric_attempt_facts,
        "numeric_scenario_facts": numeric_scenario_facts,
        "valid_numeric_parameter_ids": valid_persona_doc_parameter_ids,
        "status": scenario_stats_status,
    }

    return DashboardFooterMetrics(
        scenario_performance=scenario_performance,
        scenario_stats=scenario_stats,
        scenario_simulation_performance=scenario_simulation_performance,
        scenario_composition=scenario_composition,
    )


def compute_primary_metrics_v2(
    rubric_facts: list["RubricFactsItem"],
    standard_group_name_map: dict[str, str] | None = None,
    thresholds: dict[str, int] | None = None,
) -> DashboardPrimaryMetrics:
    """Compute primary section metrics from mv_rubric_facts.

    Primary section is now rubric-focused:
    - Rubric Heatmap: Pearson correlation matrix per rubric
    - Rubric Trend: Average score by date per standard group
    - Skill Performance: Radar chart per rubric (avg per standard group)
    """

    success_threshold, warning_threshold, _danger_threshold = _thresholds(thresholds)
    standard_group_name_map = standard_group_name_map or {}

    # --- Rubric Heatmap (same Pearson correlation logic as old compute_primary_metrics) ---
    by_rubric_chat_group: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    group_meta: dict[tuple[str, str], dict[str, str | None]] = {}
    for row in rubric_facts:
        if row.score_percent is None:
            continue
        rid = str(row.rubric_id)
        cid = str(row.chat_id)
        gid = str(row.standard_group_id)
        by_rubric_chat_group[rid][cid][gid] = float(row.score_percent)
        group_meta[(rid, gid)] = {
            "name": standard_group_name_map.get(gid, gid),
            "short_name": None,
        }

    def _pearson(xs: list[float], ys: list[float]) -> float | None:
        if len(xs) < 3 or len(ys) < 3 or len(xs) != len(ys):
            return None
        mx = mean(xs)
        my = mean(ys)
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=False))
        den_x = sum((x - mx) ** 2 for x in xs) ** 0.5
        den_y = sum((y - my) ** 2 for y in ys) ** 0.5
        den = den_x * den_y
        if den == 0:
            return None
        return num / den

    matrices = []
    avg_abs_corrs: list[float] = []
    for rid, chat_map in sorted(by_rubric_chat_group.items()):
        group_ids = sorted(
            {gid for per_group in chat_map.values() for gid in per_group.keys()}
        )
        standard_groups = [
            {
                "id": gid,
                "name": group_meta.get((rid, gid), {}).get("name") or gid,
                "short_name": group_meta.get((rid, gid), {}).get("short_name"),
                "rubric_id": rid,
            }
            for gid in group_ids
        ]
        matrix_rows = []
        best_pair: tuple[str, str, float, int] | None = None
        has_data = False
        for g1 in group_ids:
            cells = []
            for g2 in group_ids:
                pairs = [
                    (groups[g1], groups[g2])
                    for groups in chat_map.values()
                    if g1 in groups and g2 in groups
                ]
                n = len(pairs)
                r = _pearson([p[0] for p in pairs], [p[1] for p in pairs])
                corr = r if r is not None else 0.0
                if n >= 3:
                    has_data = True
                abs_corr = abs(corr)
                if g1 != g2 and n >= 3:
                    avg_abs_corrs.append(abs_corr)
                    if best_pair is None or abs_corr > abs(best_pair[2]):
                        best_pair = (g1, g2, corr, n)
                strength = (
                    "Strong"
                    if abs_corr >= 0.7
                    else "Moderate"
                    if abs_corr >= 0.4
                    else "Weak"
                    if abs_corr > 0
                    else "No Data"
                )
                if n < 3:
                    color = "#e5e7eb"
                    strength = "No Data"
                elif corr >= 0:
                    color = (
                        "#10b981"
                        if abs_corr >= 0.7
                        else "#34d399"
                        if abs_corr >= 0.4
                        else "#a7f3d0"
                    )
                else:
                    color = (
                        "#ef4444"
                        if abs_corr >= 0.7
                        else "#f87171"
                        if abs_corr >= 0.4
                        else "#fecaca"
                    )
                cells.append(
                    {
                        "rubric_id": rid,
                        "correlation": _round2(corr),
                        "p_value": None,
                        "color": color,
                        "strength": strength,
                        "data_points": n,
                    }
                )
            matrix_rows.append({"cells": cells})

        insights = None
        if best_pair is not None:
            g1, g2, r, n = best_pair
            g1_name = group_meta.get((rid, g1), {}).get("name") or g1
            g2_name = group_meta.get((rid, g2), {}).get("name") or g2
            insights = f'Top pair: "{g1_name}" vs "{g2_name}" r={r:.2f} (n={n})'

        matrices.append(
            {
                "rubric_id": rid,
                "standard_groups": standard_groups,
                "matrix": matrix_rows,
                "insights": insights,
                "has_data": has_data,
            }
        )

    heatmap_avg = mean(avg_abs_corrs) * 100 if avg_abs_corrs else None
    if heatmap_avg is None:
        heatmap_status = "neutral"
    elif heatmap_avg >= success_threshold:
        heatmap_status = "success"
    elif heatmap_avg >= warning_threshold:
        heatmap_status = "warning"
    else:
        heatmap_status = "danger"

    rubric_heatmap = {
        "matrices": matrices,
        "valid_rubric_ids": [m["rubric_id"] for m in matrices],
        "status": heatmap_status,
    }

    # --- Rubric Trend (NEW): Group by (attempt_date, standard_group_id) → mean score_percent ---
    trend_acc: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rubric_facts:
        if row.score_percent is None or row.attempt_date is None:
            continue
        gid = str(row.standard_group_id)
        day = _iso(row.attempt_date)
        trend_acc[(day, gid)].append(float(row.score_percent))

    trend_data = []
    for (day, gid), scores in sorted(trend_acc.items()):
        trend_data.append(
            {
                "date": day,
                "standard_group_id": gid,
                "standard_group_name": standard_group_name_map.get(gid, gid),
                "avg_pct": _round2(mean(scores)),
            }
        )

    trend_valid_rubric_ids = sorted(
        {str(r.rubric_id) for r in rubric_facts if r.rubric_id}
    )
    rubric_trend = {
        "trend_data": trend_data,
        "valid_rubric_ids": trend_valid_rubric_ids,
        "status": _section_status(bool(trend_data)),
    }

    # --- Skill Performance: Radar chart per rubric (avg per standard group) ---
    group_scores: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in rubric_facts:
        if row.score_percent is None:
            continue
        rid = str(row.rubric_id)
        gid = str(row.standard_group_id)
        group_scores[rid][gid].append(float(row.score_percent))

    skill_packages = []
    valid_rubrics = sorted(group_scores.keys())
    for rid in valid_rubrics:
        radar_data = []
        group_facts = []
        for gid, scores in sorted(group_scores[rid].items()):
            avg_pct = mean(scores) if scores else 0.0
            sg_name = standard_group_name_map.get(gid, gid)
            radar_data.append(
                {
                    "metric": sg_name,
                    "description": sg_name,
                    "value": _round2(avg_pct / 100.0),
                    "full_mark": 1.0,
                }
            )
            group_facts.append(
                {
                    "group_id": gid,
                    "group_name": sg_name,
                    "group_description": None,
                    "simulation_id": None,
                    "score": _round2(avg_pct),
                    "points": _round2(100.0),
                    "avg_pct": _round2(avg_pct),
                }
            )

        skill_packages.append(
            {
                "rubric_id": rid,
                "radar_data": radar_data,
                "group_facts": group_facts,
            }
        )

    skill_avg = (
        mean(
            [
                r["value"]
                for p in skill_packages
                for r in p["radar_data"]
                if r["value"] is not None
            ]
        )
        if skill_packages
        else None
    )
    skill_avg_pct = skill_avg * 100.0 if skill_avg is not None else None
    skill_status = (
        "neutral"
        if skill_avg_pct is None
        else "success"
        if skill_avg_pct >= success_threshold
        else "warning"
        if skill_avg_pct >= warning_threshold
        else "danger"
    )
    skill_performance = {
        "packages": skill_packages,
        "valid_rubric_ids": valid_rubrics,
        "status": skill_status,
    }

    return DashboardPrimaryMetrics(
        rubric_heatmap=rubric_heatmap,
        rubric_trend=rubric_trend,
        skill_performance=skill_performance,
    )


def compute_secondary_metrics_v2(
    simulation_facts: list["SimulationFactsItem"],
    persona_name_map: dict[str, str] | None = None,
    cohort_name_map: dict[str, str] | None = None,
    thresholds: dict[str, int] | None = None,
) -> DashboardSecondaryMetrics:
    """Compute secondary section metrics from mv_attempt_facts.

    Secondary section is now simulation-focused:
    - Persona Performance: Group by persona_id → avg grade_percent, trend by date
    - Cohort Performance: Group by (cohort_id, simulation_id) → pass_rate, avg_score
    - Attempt Improvement: Group by attempt_number per (profile_id, simulation_id)
    """

    success_threshold, warning_threshold, _danger_threshold = _thresholds(thresholds)
    persona_name_map = persona_name_map or {}
    cohort_name_map = cohort_name_map or {}

    # --- Persona Performance ---
    persona_rows: dict[str, dict] = defaultdict(
        lambda: {
            "scores": [],
            "sessions": 0,
            "simulation_ids": set(),
            "by_date": defaultdict(list),
        }
    )
    for row in simulation_facts:
        if row.persona_id is None or row.grade_percent is None:
            continue
        pid = str(row.persona_id)
        persona_rows[pid]["scores"].append(float(row.grade_percent))
        persona_rows[pid]["sessions"] += 1
        if row.simulation_id:
            persona_rows[pid]["simulation_ids"].add(str(row.simulation_id))
        if row.attempt_date:
            persona_rows[pid]["by_date"][row.attempt_date].append(
                float(row.grade_percent)
            )

    def persona_color(seed: str) -> str:
        h = abs(hash(seed)) % 360
        return f"hsl({h} 70% 45%)"

    persona_chart_data = []
    persona_color_junction = []
    persona_valid_sim_ids: set[str] = set()
    for pid, data in sorted(persona_rows.items()):
        trend = []
        for d, vals in sorted(data["by_date"].items()):
            trend.append(
                {
                    "date": _iso(d),
                    "score": _round2(mean(vals)),
                    "timestamp": d.toordinal(),
                    "simulation_id": next(iter(data["simulation_ids"]))
                    if data["simulation_ids"]
                    else None,
                }
            )
        sim_ids = sorted(data["simulation_ids"])
        persona_valid_sim_ids.update(sim_ids)
        color = persona_color(pid)
        persona_name = persona_name_map.get(pid, pid)
        persona_chart_data.append(
            {
                "name": persona_name,
                "score": _round2(mean(data["scores"])) if data["scores"] else None,
                "sessions": data["sessions"],
                "color": color,
                "trend_data": trend,
                "simulation_ids": sim_ids,
                "status": "neutral",
            }
        )
        persona_color_junction.append({"persona_name": persona_name, "color": color})

    persona_performance = {
        "chart_data": persona_chart_data,
        "valid_simulation_ids": sorted(persona_valid_sim_ids),
        "persona_colors_junction": persona_color_junction,
        "status": _section_status(bool(persona_chart_data)),
    }

    # --- Cohort Performance ---
    cohort_acc: dict[str, dict] = defaultdict(
        lambda: {
            "attempts": 0,
            "completed": 0,
            "passed": 0,
            "sum_score": 0.0,
            "score_count": 0,
            "profiles": set(),
            "simulation_ids": set(),
        }
    )
    cohort_daily: list[dict] = []
    simulation_facts_map: dict[tuple[str, str], dict] = defaultdict(
        lambda: {
            "attempts": 0,
            "completed": 0,
            "passed": 0,
            "sum_score": 0.0,
            "score_count": 0,
        }
    )
    daily_facts_map: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"attempts": 0, "sum_score": 0.0, "score_count": 0}
    )
    cohort_valid_sim_ids: set[str] = set()

    for row in simulation_facts:
        sim_id = str(row.simulation_id) if row.simulation_id else None
        if sim_id:
            cohort_valid_sim_ids.add(sim_id)

        day = _iso(row.attempt_date) if row.attempt_date else None

        if day and sim_id:
            df_key = (day, sim_id)
            daily_facts_map[df_key]["attempts"] += 1
            if row.grade_percent is not None:
                daily_facts_map[df_key]["sum_score"] += float(row.grade_percent)
                daily_facts_map[df_key]["score_count"] += 1

        if row.cohort_id is None:
            continue
        cohort_id = str(row.cohort_id)
        c = cohort_acc[cohort_id]
        c["attempts"] += 1
        c["completed"] += 1 if row.completed else 0
        c["passed"] += 1 if row.passed else 0
        if row.profile_id:
            c["profiles"].add(str(row.profile_id))
        if sim_id:
            c["simulation_ids"].add(sim_id)
        if row.grade_percent is not None:
            c["sum_score"] += float(row.grade_percent)
            c["score_count"] += 1

        if day:
            cohort_daily.append(
                {
                    "date": day,
                    "avg_score": _round2(float(row.grade_percent))
                    if row.grade_percent is not None
                    else None,
                    "cohort_id": cohort_id,
                }
            )

        if sim_id:
            k = (cohort_id, sim_id)
            simulation_facts_map[k]["attempts"] += 1
            simulation_facts_map[k]["completed"] += 1 if row.completed else 0
            simulation_facts_map[k]["passed"] += 1 if row.passed else 0
            if row.grade_percent is not None:
                simulation_facts_map[k]["sum_score"] += float(row.grade_percent)
                simulation_facts_map[k]["score_count"] += 1

    cohort_data = []
    for cohort_id, c in sorted(cohort_acc.items()):
        pass_rate = (c["passed"] / c["completed"] * 100) if c["completed"] > 0 else 0
        avg_score = c["sum_score"] / c["score_count"] if c["score_count"] > 0 else 0
        cohort_data.append(
            {
                "id": cohort_id,
                "name": cohort_name_map.get(cohort_id, cohort_id),
                "pass_rate": _round2(pass_rate),
                "avg_percentage_score": _round2(avg_score),
                "total_students": len(c["profiles"]),
                "passed_students": None,
                "total_attempts": c["attempts"],
                "passed_attempts": c["passed"],
                "simulation_count": len(c["simulation_ids"]),
                "required_simulations": len(c["simulation_ids"]),
                "status": "neutral",
            }
        )

    sim_facts_list = []
    for (cohort_id, sim_id), c in sorted(simulation_facts_map.items()):
        pass_rate = (c["passed"] / c["completed"] * 100) if c["completed"] > 0 else 0
        avg_score = c["sum_score"] / c["score_count"] if c["score_count"] > 0 else 0
        sim_facts_list.append(
            {
                "cohort_id": cohort_id,
                "simulation_id": sim_id,
                "pass_rate": _round2(pass_rate),
                "avg_score": _round2(avg_score),
                "attempts": c["attempts"],
            }
        )

    daily_facts = []
    for (day, sim_id), c in sorted(daily_facts_map.items()):
        avg_score = c["sum_score"] / c["score_count"] if c["score_count"] > 0 else 0
        daily_facts.append(
            {"date": day, "simulation_id": sim_id, "avg_score": _round2(avg_score)}
        )

    cohort_avg = (
        mean(
            [
                c["avg_percentage_score"]
                for c in cohort_data
                if c["avg_percentage_score"] is not None
            ]
        )
        if cohort_data
        else None
    )
    cohort_status = (
        "neutral"
        if cohort_avg is None
        else "success"
        if cohort_avg >= success_threshold
        else "warning"
        if cohort_avg >= warning_threshold
        else "danger"
    )
    cohort_performance = {
        "cohort_data": cohort_data,
        "daily_data": cohort_daily,
        "simulation_facts": sim_facts_list,
        "daily_facts": daily_facts,
        "valid_simulation_ids": sorted(cohort_valid_sim_ids),
        "status": cohort_status,
    }

    # --- Attempt Improvement ---
    # Group by (profile_id, simulation_id) sorted by attempt_number
    attempt_fact_acc: dict[tuple[str, int], dict] = defaultdict(
        lambda: {"count": 0, "sum_grade": 0.0, "sum_minutes": 0.0, "passed": 0}
    )
    attempt_chart_acc: dict[int, dict] = defaultdict(
        lambda: {"count": 0, "sum_grade": 0.0, "sum_minutes": 0.0, "passed": 0}
    )
    attempt_valid_sim_ids: set[str] = set()

    for row in simulation_facts:
        if row.simulation_id is None or row.attempt_number is None:
            continue
        sim_id = str(row.simulation_id)
        attempt_valid_sim_ids.add(sim_id)
        grade = float(row.grade_percent) if row.grade_percent is not None else 0.0
        minutes = float(row.time_taken_seconds or 0) / 60.0
        passed = 1 if row.passed else 0
        attempt_no = row.attempt_number

        k = (sim_id, attempt_no)
        attempt_fact_acc[k]["count"] += 1
        attempt_fact_acc[k]["sum_grade"] += grade
        attempt_fact_acc[k]["sum_minutes"] += minutes
        attempt_fact_acc[k]["passed"] += passed

        attempt_chart_acc[attempt_no]["count"] += 1
        attempt_chart_acc[attempt_no]["sum_grade"] += grade
        attempt_chart_acc[attempt_no]["sum_minutes"] += minutes
        attempt_chart_acc[attempt_no]["passed"] += passed

    attempt_facts = []
    for (sim_id, attempt_no), d in sorted(
        attempt_fact_acc.items(), key=lambda x: (x[0][1], x[0][0])
    ):
        cnt = d["count"]
        attempt_facts.append(
            {
                "simulation_id": sim_id,
                "attempt_no": attempt_no,
                "avg_grade": _round2(d["sum_grade"] / cnt if cnt else 0),
                "avg_minutes": _round2(d["sum_minutes"] / cnt if cnt else 0),
                "pass_rate": _round2((d["passed"] / cnt * 100) if cnt else 0),
            }
        )

    attempt_chart_data = []
    for attempt_no, d in sorted(attempt_chart_acc.items()):
        cnt = d["count"]
        attempt_chart_data.append(
            {
                "attempt": f"Attempt {attempt_no}",
                "average_score": _round2(d["sum_grade"] / cnt if cnt else 0),
                "average_time": _round2(d["sum_minutes"] / cnt if cnt else 0),
                "pass_rate": _round2((d["passed"] / cnt * 100) if cnt else 0),
            }
        )

    attempt_avg = (
        mean(
            [
                c["average_score"]
                for c in attempt_chart_data
                if c["average_score"] is not None
            ]
        )
        if attempt_chart_data
        else None
    )
    attempt_status = (
        "neutral"
        if attempt_avg is None
        else "success"
        if attempt_avg >= success_threshold
        else "warning"
        if attempt_avg >= warning_threshold
        else "danger"
    )
    attempt_improvement = {
        "chart_data": attempt_chart_data,
        "facts": attempt_facts,
        "valid_simulation_ids": sorted(attempt_valid_sim_ids),
        "status": attempt_status,
    }

    return DashboardSecondaryMetrics(
        persona_performance=persona_performance,
        cohort_performance=cohort_performance,
        attempt_improvement=attempt_improvement,
    )


def build_dashboard_bundle(
    attempts: list[AttemptFactsItem],
    daily_rows: list[DailyMetricsItem],
    chat_rows: list[ChatFactsItem],
    profile_rows: list[ProfileMetricsItem],
    first_attempt_rows: list[FirstAttemptPassItem] | None = None,
    simulation_scenario_counts: dict[str, int] | None = None,
    parameter_fields: list[Any] | None = None,
    parameters: list[Any] | None = None,
    fields: list[Any] | None = None,
    rubric_group_scores: list[RubricGroupScoreItem] | None = None,
    persona_name_map: dict[str, str] | None = None,
    cohort_name_map: dict[str, str] | None = None,
    simulation_name_map: dict[str, str] | None = None,
    scenario_name_map: dict[str, str] | None = None,
    thresholds: dict[str, int] | None = None,
) -> DashboardBundleResponse:
    """Build full dashboard get response skeleton from MV slices.

    get.py should fetch rows (filter/search only), then call this function.
    """
    return DashboardBundleResponse(
        header_metrics=compute_header_metrics(
            attempts=attempts,
            daily_rows=daily_rows,
            chat_rows=chat_rows,
            profile_rows=profile_rows,
            first_attempt_rows=first_attempt_rows,
            simulation_scenario_counts=simulation_scenario_counts,
            thresholds=thresholds,
        ),
        primary_metrics=compute_primary_metrics(
            attempts=attempts,
            daily_rows=daily_rows,
            chat_rows=chat_rows,
            profile_rows=profile_rows,
            rubric_group_scores=rubric_group_scores,
            persona_name_map=persona_name_map,
            thresholds=thresholds,
        ),
        secondary_metrics=compute_secondary_metrics(
            attempts=attempts,
            daily_rows=daily_rows,
            chat_rows=chat_rows,
            profile_rows=profile_rows,
            cohort_name_map=cohort_name_map,
            rubric_group_scores=rubric_group_scores,
            thresholds=thresholds,
        ),
        footer_metrics=compute_footer_metrics(
            attempts=attempts,
            daily_rows=daily_rows,
            chat_rows=chat_rows,
            profile_rows=profile_rows,
            parameter_fields=parameter_fields,
            parameters=parameters,
            fields=fields,
            simulation_name_map=simulation_name_map,
            scenario_name_map=scenario_name_map,
            thresholds=thresholds,
        ),
    )
