"""Leaderboard calculation/business logic for get.py.

This module defines the initial computation skeleton for leaderboard sections.
The route should pass raw MV slices; this module returns deterministic output
shapes that can be expanded without changing route wiring.
"""

import json
from collections import defaultdict
from datetime import date, datetime
from statistics import mean
from typing import Any
from uuid import UUID

from app.infra.leaderboard.types import (
    LeaderboardAccoladeWinner,
    LeaderboardAccoladeWinners,
    LeaderboardDataRow,
    LeaderboardHeaderMetrics,
    LeaderboardMetric,
    LeaderboardMetricsEntry,
    LeaderboardSections,
    LeaderboardSectionStatus,
)
from app.tools.entries.attempt_chat.types import (
    ChatItem,
    GetAttemptChatResponse,
)
from app.tools.entries.attempt_message.types import GetAttemptMessageResponse

# Type aliases for deprecated v1 types (modules deleted in DELETE OLD VIEWS)
AttemptFactsItem = Any
ChatFactsItem = Any
DailyMetricsItem = Any
ProfileMetricsItem = Any


def _metric(
    value: float | int | None,
    *,
    method: str = "mv_profile_metrics",
    key_field: str | None = None,
    trend_data: list[str] | None = None,
    data_points: list[str] | None = None,
    hover: str | None = None,
) -> LeaderboardMetric:
    return LeaderboardMetric(
        has_data=value is not None,
        method=method,
        current_value=value,
        key_field=key_field,
        trend_data=trend_data or [],
        data_points=data_points or [],
        hover=hover,
    )


def _round_int(value: float | int | None) -> int | None:
    if value is None:
        return None
    return int(round(float(value)))


def _json_point(**kwargs: object) -> str:
    return json.dumps(kwargs, separators=(",", ":"), default=str)


def _format_dt(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def _profile_context(
    profile_id: str,
    attempts_by_profile: dict[str, list[AttemptFactsItem]],
    chats_by_profile: dict[str, list[ChatFactsItem]],
) -> dict[str, list]:
    attempts = sorted(
        attempts_by_profile.get(profile_id, []),
        key=lambda a: a.attempt_created_at or datetime.min,
    )
    chats = sorted(
        chats_by_profile.get(profile_id, []),
        key=lambda c: c.grade_created_at or c.chat_created_at,
    )
    return {"attempts": attempts, "chats": chats}


def _section(has_data: bool, note: str | None = None) -> LeaderboardSectionStatus:
    return LeaderboardSectionStatus(
        has_data=has_data,
        status="neutral" if has_data else "empty",
        note=note,
    )


def build_leaderboard_rows(
    profile_rows: list[ProfileMetricsItem],
    profile_name_by_id: dict[str, str | None] | None = None,
    attempts: list[AttemptFactsItem] | None = None,
    chat_rows: list[ChatFactsItem] | None = None,
    sort_by: str = "highest_score",
    sort_order: str = "desc",
    rank_offset: int = 0,
) -> list[LeaderboardDataRow]:
    """Build minimal leaderboard rows from profile-level MV rows."""
    rows: list[LeaderboardDataRow] = []
    profile_name_by_id = profile_name_by_id or {}
    attempts_by_profile: dict[str, list[AttemptFactsItem]] = defaultdict(list)
    chats_by_profile: dict[str, list[ChatFactsItem]] = defaultdict(list)
    for item in attempts or []:
        if item.profile_id is not None:
            attempts_by_profile[str(item.profile_id)].append(item)
    for item in chat_rows or []:
        if item.profile_id is not None:
            chats_by_profile[str(item.profile_id)].append(item)

    for row in profile_rows:
        profile_id = str(row.profile_id)
        context = _profile_context(profile_id, attempts_by_profile, chats_by_profile)
        profile_attempts = context["attempts"]
        profile_chats = context["chats"]

        score_points = [
            _json_point(
                date=_format_dt(a.attempt_created_at),
                value=_round_int(a.score_percent),
                attempt_id=str(a.attempt_id),
            )
            for a in profile_attempts
            if a.score_percent is not None
        ]
        score_trend = list(score_points[-12:])
        top_score = max(
            (
                _round_int(a.score_percent)
                for a in profile_attempts
                if a.score_percent is not None
            ),
            default=0,
        )

        chat_message_points = [
            _json_point(
                date=_format_dt(c.chat_created_at),
                value=c.num_messages_total,
                chat_id=str(c.chat_id),
            )
            for c in profile_chats
            if c.num_messages_total is not None
        ]
        chat_message_trend = list(chat_message_points[-12:])

        response_values: list[int] = [
            int(v)
            for c in profile_chats
            for v in (c.message_time_taken_seconds or [])
            if v is not None
        ]
        response_mean = (
            int(round(sum(response_values) / len(response_values)))
            if response_values
            else 0
        )
        response_points = [
            _json_point(
                date=_format_dt(c.chat_created_at),
                value=(
                    int(
                        round(
                            sum(c.message_time_taken_seconds)
                            / len(c.message_time_taken_seconds)
                        )
                    )
                    if c.message_time_taken_seconds
                    else 0
                ),
                chat_id=str(c.chat_id),
            )
            for c in profile_chats
        ]
        response_trend = list(response_points[-12:])

        time_points = [
            _json_point(
                date=_format_dt(c.chat_created_at),
                value=(
                    int(round((c.time_taken or 0) / 60.0))
                    if c.time_taken is not None
                    else 0
                ),
                chat_id=str(c.chat_id),
            )
            for c in profile_chats
        ]
        time_trend = list(time_points[-12:])

        improvement_points = [
            _json_point(
                date=_format_dt(a.attempt_created_at),
                value=_round_int(a.score_percent),
                attempt_id=str(a.attempt_id),
            )
            for a in profile_attempts
            if a.score_percent is not None
        ]
        improvement_trend = list(improvement_points[-12:])

        perfect_points = [
            _json_point(
                date=_format_dt(a.attempt_created_at),
                value=1,
                attempt_id=str(a.attempt_id),
            )
            for a in profile_attempts
            if (a.score_percent or 0) >= 100
        ]
        perfect_trend = list(perfect_points[-12:])

        quickest_points = [
            _json_point(
                date=_format_dt(c.chat_created_at),
                value=int(round((c.time_taken or 0) / 60.0)),
                chat_id=str(c.chat_id),
            )
            for c in profile_chats
            if c.passed and c.time_taken is not None
        ]
        quickest_trend = list(quickest_points[-12:])

        highest_score_avg = (
            _round_int(row.highest_score)
            if row.highest_score is not None
            else (_round_int(row.avg_score) if row.avg_score is not None else None)
        )
        metrics_entry = LeaderboardMetricsEntry(
            total_attempts=_metric(
                row.total_attempts,
                method="countDistinct",
                key_field="total_attempts",
                trend_data=[],
                data_points=[
                    _json_point(
                        date=_format_dt(a.attempt_created_at),
                        value=1,
                        attempt_id=str(a.attempt_id),
                    )
                    for a in profile_attempts
                ],
                hover=f"attempts={row.total_attempts}",
            ),
            highest_score_avg=_metric(
                highest_score_avg,
                method="max",
                key_field="highest_score",
                trend_data=score_trend,
                data_points=score_points,
                hover=f"top={top_score}%",
            ),
            messages_per_session=_metric(
                _round_int(row.avg_messages_per_session)
                if row.avg_messages_per_session is not None
                else None,
                method="avg",
                key_field="avg_messages_per_session",
                trend_data=chat_message_trend,
                data_points=chat_message_points,
                hover=f"samples={len(chat_message_points)}",
            ),
            persona_response_seconds=_metric(
                _round_int(row.avg_persona_response_sec)
                if row.avg_persona_response_sec is not None
                else None,
                method="avg",
                key_field="avg_persona_response_sec",
                trend_data=response_trend,
                data_points=response_points,
                hover=f"mean={response_mean}s; lower=better",
            ),
            time_spent_minutes=_metric(
                _round_int(row.total_time_minutes)
                if row.total_time_minutes is not None
                else None,
                method="sum",
                key_field="total_time_minutes",
                trend_data=time_trend,
                data_points=time_points,
                hover=f"total={_round_int(row.total_time_minutes) or 0} min",
            ),
            improvement_rate_per_day=_metric(
                _round_int(row.improvement_rate)
                if row.improvement_rate is not None
                else None,
                method="delta/day",
                key_field="improvement_rate",
                trend_data=improvement_trend,
                data_points=improvement_points,
                hover="based on best-grade deltas over time",
            ),
            perfect_score_count=_metric(
                row.perfect_score_count,
                method="count",
                key_field="perfect_score_count",
                trend_data=perfect_trend,
                data_points=perfect_points,
                hover=f"perfect={row.perfect_score_count}",
            ),
            quickest_pass_minutes=_metric(
                _round_int(row.quickest_pass_minutes)
                if row.quickest_pass_minutes is not None
                else None,
                method="min",
                key_field="quickest_pass_minutes",
                trend_data=quickest_trend,
                data_points=quickest_points,
                hover="lower is better",
            ),
        )
        rows.append(
            LeaderboardDataRow(
                profile_id=profile_id,
                name=profile_name_by_id.get(profile_id),
                simulation_ids=[str(sim_id) for sim_id in row.simulation_ids],
                scenario_ids=[str(scenario_id) for scenario_id in row.scenario_ids],
                metrics_entry=metrics_entry,
            )
        )

    sort_key_map = {
        "highest_score": "highest_score_avg",
        "highestScore": "highest_score_avg",
        "total_attempts": "total_attempts",
        "totalAttempts": "total_attempts",
        "avg_messages": "messages_per_session",
        "messagesPerSession": "messages_per_session",
        "persona_response_seconds": "persona_response_seconds",
        "personaResponseTimes": "persona_response_seconds",
        "time_spent_minutes": "time_spent_minutes",
        "timeSpent": "time_spent_minutes",
        "improvement_rate_per_day": "improvement_rate_per_day",
        "improvement": "improvement_rate_per_day",
        "perfect_score_count": "perfect_score_count",
        "quickest_pass_minutes": "quickest_pass_minutes",
    }
    selected_metric = sort_key_map.get(sort_by, "highest_score_avg")
    reverse = sort_order.lower() != "asc"

    def _sort_value(row: LeaderboardDataRow) -> float:
        raw = _metric_value(row, selected_metric)
        if raw is None:
            return float("-inf")
        return float(raw)

    rows.sort(
        key=lambda r: (
            _sort_value(r),
            float(_metric_value(r, "highest_score_avg") or 0),
            float(_metric_value(r, "total_attempts") or 0),
            r.profile_id or "",
        ),
        reverse=reverse,
    )

    for i, row in enumerate(rows, start=1):
        row.rank = rank_offset + i
    return rows


def _compute_header_metrics(
    profile_rows: list[ProfileMetricsItem],
) -> LeaderboardHeaderMetrics:
    total_profiles = len({row.profile_id for row in profile_rows})
    total_attempts = sum(row.total_attempts for row in profile_rows)

    avg_scores = [
        float(row.avg_score) for row in profile_rows if row.avg_score is not None
    ]
    average_score = round(sum(avg_scores) / len(avg_scores), 2) if avg_scores else None

    perfect_scores = sum(row.perfect_score_count for row in profile_rows)

    return LeaderboardHeaderMetrics(
        total_profiles=_metric(total_profiles, key_field="profile_id"),
        total_attempts=_metric(total_attempts, key_field="total_attempts"),
        average_score=_metric(average_score, key_field="avg_score"),
        perfect_scores=_metric(perfect_scores, key_field="perfect_score_count"),
    )


def _metric_value(row: LeaderboardDataRow, key: str) -> float | int | None:
    if not row.metrics_entry:
        return None
    metric = getattr(row.metrics_entry, key, None)
    if not metric:
        return None
    return metric.current_value


def _pick_max(rows: list[LeaderboardDataRow], key: str) -> LeaderboardDataRow | None:
    if not rows:
        return None
    with_values = [r for r in rows if _metric_value(r, key) is not None]
    if not with_values:
        return None
    return max(
        with_values,
        key=lambda r: float(_metric_value(r, key) or 0),
    )


def _pick_min_positive(
    rows: list[LeaderboardDataRow], key: str
) -> LeaderboardDataRow | None:
    with_values = [
        r
        for r in rows
        if _metric_value(r, key) is not None and float(_metric_value(r, key) or 0) > 0
    ]
    if not with_values:
        return None
    return min(with_values, key=lambda r: float(_metric_value(r, key) or 0))


def _winner(
    row: LeaderboardDataRow | None,
    metric_key: str,
    details_fmt: str,
) -> LeaderboardAccoladeWinner | None:
    if not row:
        return None
    value = _metric_value(row, metric_key)
    if value is None:
        return None
    return LeaderboardAccoladeWinner(
        profile_id=row.profile_id,
        name=row.name,
        value=value,
        details=details_fmt.format(value=value),
    )


def compute_accolade_winners(
    rows: list[LeaderboardDataRow],
) -> LeaderboardAccoladeWinners:
    """Compute deterministic accolade winners from normalized leaderboard rows."""
    highest_scorer = _pick_max(rows, "highest_score_avg")
    perfect_score = _pick_max(rows, "perfect_score_count")
    longest_convo = _pick_max(rows, "messages_per_session")
    response_times = _pick_min_positive(rows, "persona_response_seconds")
    quickest_pass = _pick_min_positive(rows, "quickest_pass_minutes")
    the_persistent = _pick_max(rows, "total_attempts")
    marathon_runner = _pick_max(rows, "time_spent_minutes")
    rapid_riser = _pick_max(rows, "improvement_rate_per_day")

    return LeaderboardAccoladeWinners(
        highest_scorer=_winner(highest_scorer, "highest_score_avg", "{value:.0f} avg"),
        perfect_score=_winner(
            perfect_score, "perfect_score_count", "{value:.0f} perfect"
        ),
        longest_convo=_winner(
            longest_convo, "messages_per_session", "{value:.0f} msgs/session"
        ),
        response_times=_winner(
            response_times, "persona_response_seconds", "{value:.0f}s"
        ),
        quickest_pass=_winner(
            quickest_pass, "quickest_pass_minutes", "{value:.0f} min"
        ),
        the_persistent=_winner(
            the_persistent, "total_attempts", "{value:.0f} attempts"
        ),
        marathon_runner=_winner(
            marathon_runner, "time_spent_minutes", "{value:.0f} min"
        ),
        rapid_riser=_winner(
            rapid_riser, "improvement_rate_per_day", "{value:.0f} pts/day"
        ),
    )


def build_leaderboard_sections(
    attempts: list[AttemptFactsItem],
    chat_rows: list[ChatFactsItem],
    daily_rows: list[DailyMetricsItem],
    profile_rows: list[ProfileMetricsItem],
    rows: list[LeaderboardDataRow] | None = None,
) -> LeaderboardSections:
    """Build leaderboard section-computation skeleton from four MV slices."""
    row_data = rows or []
    return LeaderboardSections(
        header_metrics=_compute_header_metrics(profile_rows),
        rankings=_section(bool(profile_rows), "Derived from mv_profile_metrics"),
        accolades=_section(
            bool(profile_rows),
            "Derived from mv_profile_metrics rank metrics",
        ),
        trends=_section(
            bool(daily_rows) or bool(chat_rows),
            "Derived from mv_daily_metrics and mv_chat_facts",
        ),
        filters=_section(
            bool(attempts) or bool(profile_rows),
            "Filter IDs sourced from mv_profile_facts and mv_profile_metrics",
        ),
        accolade_winners=compute_accolade_winners(row_data),
    )


# ---------------------------------------------------------------------------
# v2 functions — operate on ChatItem (chat-grain from attempt_chat_mv)
# ---------------------------------------------------------------------------


def _format_date(d: date | None) -> str | None:
    """Format a date as ISO string."""
    if d is None:
        return None
    return d.isoformat()


def build_leaderboard_rows_v2(
    chat_items: list[ChatItem],
    profile_name_by_id: dict[str, str | None] | None = None,
    sort_by: str = "highest_score",
    sort_order: str = "desc",
    rank_offset: int = 0,
    message_stats_map: dict | None = None,
) -> list[LeaderboardDataRow]:
    """Build leaderboard rows from chat-grain items (attempt_chat_mv).

    Aggregates chat-level rows to profile-level metrics entirely in Python.
    """
    rows: list[LeaderboardDataRow] = []
    profile_name_by_id = profile_name_by_id or {}
    message_stats_map = message_stats_map or {}

    # Group items by profile_id
    items_by_profile: dict[str, list[ChatItem]] = defaultdict(list)
    for item in chat_items:
        items_by_profile[str(item.profile_id)].append(item)

    for profile_id, items in items_by_profile.items():
        # Sort items chronologically by attempt_date
        sorted_items = sorted(items, key=lambda x: x.attempt_date or date.min)

        # --- Aggregate profile-level metrics ---
        attempt_ids = {item.attempt_id for item in items}
        total_attempts = len(attempt_ids)

        grade_values = [
            item.grade_percent for item in items if item.grade_percent is not None
        ]
        highest_score = max(grade_values) if grade_values else None
        avg_score = mean(grade_values) if grade_values else None

        msg_counts = [
            message_stats_map[item.chat_id].num_messages_total
            for item in items
            if item.chat_id in message_stats_map
        ]
        avg_messages_per_session = mean(msg_counts) if msg_counts else None

        response_secs = [
            message_stats_map[item.chat_id].avg_response_sec
            for item in items
            if item.chat_id in message_stats_map
            and message_stats_map[item.chat_id].avg_response_sec is not None
        ]
        avg_persona_response_sec = mean(response_secs) if response_secs else None

        time_values = [
            item.grade_time_taken for item in items if item.grade_time_taken is not None
        ]
        total_time_minutes = sum(time_values) / 60.0 if time_values else None

        # Improvement rate: compare first half vs second half of grade_percents
        improvement_rate: float | None = None
        if len(grade_values) >= 2:
            # Use sorted_items order (chronological) for grade values
            chrono_grades = [
                item.grade_percent
                for item in sorted_items
                if item.grade_percent is not None
            ]
            if len(chrono_grades) >= 2:
                mid_g = len(chrono_grades) // 2
                first_half = chrono_grades[:mid_g]
                second_half = chrono_grades[mid_g:]
                if first_half and second_half:
                    improvement_rate = mean(second_half) - mean(first_half)

        perfect_score_count = sum(
            1
            for item in items
            if item.grade_percent is not None and item.grade_percent >= 100
        )

        passed_with_time = [
            item.grade_time_taken / 60.0
            for item in items
            if item.grade_passed and item.grade_time_taken is not None
        ]
        quickest_pass_minutes = min(passed_with_time) if passed_with_time else None

        simulation_ids = list({str(item.simulation_id) for item in items})
        scenario_ids = list(
            {str(item.scenario_id) for item in items if item.scenario_id is not None}
        )

        # --- Build trend data points (chronological) ---
        score_points = [
            _json_point(
                date=_format_date(item.attempt_date),
                value=_round_int(item.grade_percent),
                chat_id=str(item.chat_id),
            )
            for item in sorted_items
            if item.grade_percent is not None
        ]
        score_trend = list(score_points[-12:])

        top_score = max(
            (
                _round_int(item.grade_percent)
                for item in items
                if item.grade_percent is not None
            ),
            default=0,
        )

        chat_message_points = [
            _json_point(
                date=_format_date(item.attempt_date),
                value=message_stats_map[item.chat_id].num_messages_total,
                chat_id=str(item.chat_id),
            )
            for item in sorted_items
            if item.chat_id in message_stats_map
        ]
        chat_message_trend = list(chat_message_points[-12:])

        response_mean = int(round(mean(response_secs))) if response_secs else 0
        response_points = [
            _json_point(
                date=_format_date(item.attempt_date),
                value=int(round(message_stats_map[item.chat_id].avg_response_sec))
                if (
                    item.chat_id in message_stats_map
                    and message_stats_map[item.chat_id].avg_response_sec is not None
                )
                else 0,
                chat_id=str(item.chat_id),
            )
            for item in sorted_items
        ]
        response_trend = list(response_points[-12:])

        time_points = [
            _json_point(
                date=_format_date(item.attempt_date),
                value=(
                    int(round((item.grade_time_taken or 0) / 60.0))
                    if item.grade_time_taken is not None
                    else 0
                ),
                chat_id=str(item.chat_id),
            )
            for item in sorted_items
        ]
        time_trend = list(time_points[-12:])

        improvement_points = [
            _json_point(
                date=_format_date(item.attempt_date),
                value=_round_int(item.grade_percent),
                chat_id=str(item.chat_id),
            )
            for item in sorted_items
            if item.grade_percent is not None
        ]
        improvement_trend = list(improvement_points[-12:])

        perfect_points = [
            _json_point(
                date=_format_date(item.attempt_date),
                value=1,
                chat_id=str(item.chat_id),
            )
            for item in sorted_items
            if item.grade_percent is not None and item.grade_percent >= 100
        ]
        perfect_trend = list(perfect_points[-12:])

        quickest_points = [
            _json_point(
                date=_format_date(item.attempt_date),
                value=int(round((item.grade_time_taken or 0) / 60.0)),
                chat_id=str(item.chat_id),
            )
            for item in sorted_items
            if item.grade_passed and item.grade_time_taken is not None
        ]
        quickest_trend = list(quickest_points[-12:])

        # --- Build metrics entry ---
        highest_score_avg = (
            _round_int(highest_score)
            if highest_score is not None
            else (_round_int(avg_score) if avg_score is not None else None)
        )
        metrics_entry = LeaderboardMetricsEntry(
            total_attempts=_metric(
                total_attempts,
                method="countDistinct",
                key_field="total_attempts",
                trend_data=[],
                data_points=[
                    _json_point(
                        date=_format_date(item.attempt_date),
                        value=1,
                        attempt_id=str(item.attempt_id),
                    )
                    for item in sorted_items
                ],
                hover=f"attempts={total_attempts}",
            ),
            highest_score_avg=_metric(
                highest_score_avg,
                method="max",
                key_field="highest_score",
                trend_data=score_trend,
                data_points=score_points,
                hover=f"top={top_score}%",
            ),
            messages_per_session=_metric(
                _round_int(avg_messages_per_session)
                if avg_messages_per_session is not None
                else None,
                method="avg",
                key_field="avg_messages_per_session",
                trend_data=chat_message_trend,
                data_points=chat_message_points,
                hover=f"samples={len(chat_message_points)}",
            ),
            persona_response_seconds=_metric(
                _round_int(avg_persona_response_sec)
                if avg_persona_response_sec is not None
                else None,
                method="avg",
                key_field="avg_persona_response_sec",
                trend_data=response_trend,
                data_points=response_points,
                hover=f"mean={response_mean}s; lower=better",
            ),
            time_spent_minutes=_metric(
                _round_int(total_time_minutes)
                if total_time_minutes is not None
                else None,
                method="sum",
                key_field="total_time_minutes",
                trend_data=time_trend,
                data_points=time_points,
                hover=f"total={_round_int(total_time_minutes) or 0} min",
            ),
            improvement_rate_per_day=_metric(
                _round_int(improvement_rate) if improvement_rate is not None else None,
                method="delta/day",
                key_field="improvement_rate",
                trend_data=improvement_trend,
                data_points=improvement_points,
                hover="based on best-grade deltas over time",
            ),
            perfect_score_count=_metric(
                perfect_score_count,
                method="count",
                key_field="perfect_score_count",
                trend_data=perfect_trend,
                data_points=perfect_points,
                hover=f"perfect={perfect_score_count}",
            ),
            quickest_pass_minutes=_metric(
                _round_int(quickest_pass_minutes)
                if quickest_pass_minutes is not None
                else None,
                method="min",
                key_field="quickest_pass_minutes",
                trend_data=quickest_trend,
                data_points=quickest_points,
                hover="lower is better",
            ),
        )
        rows.append(
            LeaderboardDataRow(
                profile_id=profile_id,
                name=profile_name_by_id.get(profile_id),
                simulation_ids=simulation_ids,
                scenario_ids=scenario_ids,
                metrics_entry=metrics_entry,
            )
        )

    # --- Sort ---
    sort_key_map = {
        "highest_score": "highest_score_avg",
        "highestScore": "highest_score_avg",
        "total_attempts": "total_attempts",
        "totalAttempts": "total_attempts",
        "avg_messages": "messages_per_session",
        "messagesPerSession": "messages_per_session",
        "persona_response_seconds": "persona_response_seconds",
        "personaResponseTimes": "persona_response_seconds",
        "time_spent_minutes": "time_spent_minutes",
        "timeSpent": "time_spent_minutes",
        "improvement_rate_per_day": "improvement_rate_per_day",
        "improvement": "improvement_rate_per_day",
        "perfect_score_count": "perfect_score_count",
        "quickest_pass_minutes": "quickest_pass_minutes",
    }
    selected_metric = sort_key_map.get(sort_by, "highest_score_avg")
    reverse = sort_order.lower() != "asc"

    def _sort_value(row: LeaderboardDataRow) -> float:
        raw = _metric_value(row, selected_metric)
        if raw is None:
            return float("-inf")
        return float(raw)

    rows.sort(
        key=lambda r: (
            _sort_value(r),
            float(_metric_value(r, "highest_score_avg") or 0),
            float(_metric_value(r, "total_attempts") or 0),
            r.profile_id or "",
        ),
        reverse=reverse,
    )

    for i, row in enumerate(rows, start=1):
        row.rank = rank_offset + i
    return rows


def _compute_header_metrics_v2(
    chat_items: list[ChatItem],
) -> LeaderboardHeaderMetrics:
    """Compute header metrics from chat-grain items."""
    total_profiles = len({item.profile_id for item in chat_items})
    total_attempts = len({item.attempt_id for item in chat_items})

    grade_values = [
        float(item.grade_percent)
        for item in chat_items
        if item.grade_percent is not None
    ]
    average_score = round(mean(grade_values), 2) if grade_values else None

    perfect_scores = sum(
        1
        for item in chat_items
        if item.grade_percent is not None and item.grade_percent >= 100
    )

    return LeaderboardHeaderMetrics(
        total_profiles=_metric(total_profiles, key_field="profile_id"),
        total_attempts=_metric(total_attempts, key_field="total_attempts"),
        average_score=_metric(average_score, key_field="avg_score"),
        perfect_scores=_metric(perfect_scores, key_field="perfect_score_count"),
    )


def build_leaderboard_sections_v2(
    chat_items: list[ChatItem],
    rows: list[LeaderboardDataRow] | None = None,
) -> LeaderboardSections:
    """Build leaderboard section skeleton from attempt_chat_mv chat-grain rows."""
    row_data = rows or []
    has_data = bool(chat_items)
    return LeaderboardSections(
        header_metrics=_compute_header_metrics_v2(chat_items),
        rankings=_section(has_data, "Derived from attempt_chat_mv"),
        accolades=_section(has_data, "Derived from attempt_chat_mv rank metrics"),
        trends=_section(has_data, "Derived from attempt_chat_mv"),
        filters=_section(has_data, "Filter IDs sourced from attempt_chat_mv"),
        accolade_winners=compute_accolade_winners(row_data),
    )


# ---------------------------------------------------------------------------
# v3 functions — operate on GetAttemptChatResponse + GetAttemptMessageResponse
# ---------------------------------------------------------------------------


def compute_message_stats(
    attempt_messages: list[GetAttemptMessageResponse],
) -> dict[UUID, dict[str, Any]]:
    """Compute per-chat message stats from attempt_message_mv rows.

    Returns dict keyed by chat_id with:
      - num_messages_total: int
      - avg_response_sec: float | None
    """
    msgs_by_chat: dict[UUID, list[GetAttemptMessageResponse]] = defaultdict(list)
    for msg in attempt_messages:
        if msg.chat_id:
            msgs_by_chat[msg.chat_id].append(msg)

    stats: dict[UUID, dict[str, Any]] = {}
    for chat_id, msgs in msgs_by_chat.items():
        sorted_msgs = sorted(msgs, key=lambda m: m.created_at or datetime.min)
        num_messages = len(sorted_msgs)

        # Compute response times: time between consecutive query→response pairs
        response_times: list[float] = []
        for i in range(1, len(sorted_msgs)):
            prev = sorted_msgs[i - 1]
            curr = sorted_msgs[i]
            if (
                prev.type == "query"
                and curr.type == "response"
                and prev.created_at
                and curr.created_at
            ):
                delta = (curr.created_at - prev.created_at).total_seconds()
                if delta >= 0:
                    response_times.append(delta)

        avg_response_sec = round(mean(response_times), 2) if response_times else None

        stats[chat_id] = {
            "num_messages_total": num_messages,
            "avg_response_sec": avg_response_sec,
        }

    return stats


def _attempt_chat_to_chat_item(
    ac: GetAttemptChatResponse,
    message_stats: dict[UUID, dict[str, Any]],
) -> ChatItem:
    """Convert GetAttemptChatResponse to ChatItem with message stats enrichment."""
    stats = message_stats.get(ac.chat_id, {}) if ac.chat_id else {}
    return ChatItem(
        chat_id=ac.chat_id,
        attempt_id=ac.attempt_id,
        chat_entry_id=ac.chat_entry_id,
        group_id=ac.group_id,
        profile_id=ac.profile_id,
        cohort_id=ac.cohort_id,
        department_id=ac.department_id,
        simulation_id=ac.simulation_id,
        scenario_id=ac.scenario_id,
        persona_ids=ac.persona_ids,
        rubric_id=ac.rubric_id,
        grade_score=ac.grade_score,
        grade_total_points=ac.grade_total_points,
        grade_pass_points=ac.grade_pass_points,
        grade_passed=ac.grade_passed,
        grade_time_taken=ac.grade_time_taken,
        completed=ac.completed or False,
        attempt_number=ac.attempt_number or 0,
        chat_created_at=ac.chat_created_at,
        attempt_date=ac.attempt_date,
        attempt_type=ac.attempt_type,
        is_archived=ac.is_archived or False,
        infinite_mode=ac.infinite_mode or False,
        num_messages_total=stats.get("num_messages_total", 0),
        avg_response_sec=stats.get("avg_response_sec"),
    )


def build_leaderboard_sections_v3(
    attempt_chats: list[GetAttemptChatResponse],
    attempt_messages: list[GetAttemptMessageResponse],
    rows: list[LeaderboardDataRow] | None = None,
) -> LeaderboardSections:
    """Build leaderboard sections from raw MV entries."""
    message_stats = compute_message_stats(attempt_messages)
    chat_items = [_attempt_chat_to_chat_item(ac, message_stats) for ac in attempt_chats]
    return build_leaderboard_sections_v2(chat_items, rows)


def build_leaderboard_rows_v3(
    attempt_chats: list[GetAttemptChatResponse],
    attempt_messages: list[GetAttemptMessageResponse],
    profile_name_by_id: dict[str, str | None] | None = None,
    sort_by: str = "highest_score",
    sort_order: str = "desc",
    rank_offset: int = 0,
) -> list[LeaderboardDataRow]:
    """Build leaderboard rows from raw MV entries."""
    message_stats = compute_message_stats(attempt_messages)

    # Convert to ChatItems with enriched message stats
    chat_items = [_attempt_chat_to_chat_item(ac, message_stats) for ac in attempt_chats]

    # Build a message_stats_map compatible with v2 (keyed by chat_id)
    class _Stats:
        __slots__ = ("num_messages_total", "avg_response_sec")

        def __init__(self, num: int, avg: float | None):
            self.num_messages_total = num
            self.avg_response_sec = avg

    compat_map = {
        chat_id: _Stats(s["num_messages_total"], s["avg_response_sec"])
        for chat_id, s in message_stats.items()
    }

    return build_leaderboard_rows_v2(
        chat_items,
        profile_name_by_id=profile_name_by_id,
        sort_by=sort_by,
        sort_order=sort_order,
        rank_offset=rank_offset,
        message_stats_map=compat_map,
    )
