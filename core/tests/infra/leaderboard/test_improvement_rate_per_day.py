"""Regression tests for the `improvement_rate_per_day` leaderboard metric.

The metric was computed as a *raw point delta* (mean of the second half of a
student's grade percents minus the mean of the first half) and surfaced
unchanged under the name ``improvement_rate_per_day`` — never divided by the
elapsed time span. It also powers the "Rapid Riser" accolade (fastest riser).

Consequence: a student who gained 40 pts over 2 days and one who gained the
same 40 pts over 100 days both scored 40 and tied — the accolade ignored time
span entirely. The fix divides the point delta by the day span between the
first and last graded attempt (floored to 1 day to guard divide-by-zero), so
the value is a true per-day rate and the faster riser ranks higher.

Modular: deps (the ChatItems) are built in-process and passed straight into
``build_leaderboard_rows_v2`` / ``compute_accolade_winners``. No DB/Redis/MV.
"""

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.infra.leaderboard.permissions import (
    build_leaderboard_rows_v2,
    compute_accolade_winners,
)
from app.tools.entries.attempt_chat.types import ChatItem

pytestmark = pytest.mark.asyncio


def _chat(
    profile_id,
    *,
    grade_score: int,
    attempt_date: date,
) -> ChatItem:
    """A real ChatItem with grade_percent == grade_score (total = 100 pts)."""
    return ChatItem(
        chat_id=uuid4(),
        attempt_id=uuid4(),
        profile_id=profile_id,
        grade_score=grade_score,
        grade_total_points=100,
        chat_created_at=datetime(
            attempt_date.year,
            attempt_date.month,
            attempt_date.day,
            tzinfo=timezone.utc,
        ),
        attempt_date=attempt_date,
    )


def _rate(rows, profile_id):
    """Pull the improvement_rate_per_day current_value for a profile."""
    row = next(r for r in rows if r.profile_id == str(profile_id))
    return row.metrics_entry.improvement_rate_per_day.current_value


async def test_same_gain_different_span_yields_different_per_day_rate():
    """Equal +40 point gain over 2 days vs 100 days → different per-day rates.

    Pre-fix both were the raw delta (40.0) and tied. Post-fix the 2-day
    student's rate is far higher (20.0 vs 0.4) — time span now matters.
    """
    base = date(2026, 1, 1)
    fast = uuid4()  # 50 -> 90 over 2 days
    slow = uuid4()  # 50 -> 90 over 100 days

    items = [
        _chat(fast, grade_score=50, attempt_date=base),
        _chat(fast, grade_score=90, attempt_date=base + timedelta(days=2)),
        _chat(slow, grade_score=50, attempt_date=base),
        _chat(slow, grade_score=90, attempt_date=base + timedelta(days=100)),
    ]

    rows = build_leaderboard_rows_v2(items)

    fast_rate = _rate(rows, fast)
    slow_rate = _rate(rows, slow)

    # 40-point delta / span: 40/2 == 20.0 ; 40/100 == 0.4.
    assert fast_rate == pytest.approx(20.0)
    assert slow_rate == pytest.approx(0.4)
    # The whole point: same gain, different span → no longer a tie.
    assert fast_rate > slow_rate


async def test_rapid_riser_accolade_rewards_the_faster_riser():
    """The "Rapid Riser" accolade winner is the student who rose fastest.

    With identical +40 gains, the 2-day riser must win over the 100-day riser.
    Pre-fix this was a tie (both 40), so the winner was arbitrary.
    """
    base = date(2026, 1, 1)
    fast = uuid4()
    slow = uuid4()

    items = [
        _chat(fast, grade_score=50, attempt_date=base),
        _chat(fast, grade_score=90, attempt_date=base + timedelta(days=2)),
        _chat(slow, grade_score=50, attempt_date=base),
        _chat(slow, grade_score=90, attempt_date=base + timedelta(days=100)),
    ]

    rows = build_leaderboard_rows_v2(items)
    winners = compute_accolade_winners(rows)

    assert winners.rapid_riser is not None
    assert winners.rapid_riser.profile_id == str(fast)
    assert winners.rapid_riser.value == pytest.approx(20.0)
    # Details now render the fractional per-day rate (was "{:.0f}").
    assert winners.rapid_riser.details == "20.0 pts/day"


async def test_same_day_attempts_do_not_divide_by_zero():
    """Two graded attempts on the same calendar day must not raise.

    The day span is 0; flooring to a 1-day minimum keeps the rate finite and
    equal to the raw point delta (40 pts over a floored 1 day == 40.0).
    """
    same_day = date(2026, 3, 15)
    profile_id = uuid4()

    items = [
        _chat(profile_id, grade_score=50, attempt_date=same_day),
        _chat(profile_id, grade_score=90, attempt_date=same_day),
    ]

    # Must not raise ZeroDivisionError.
    rows = build_leaderboard_rows_v2(items)

    assert _rate(rows, profile_id) == pytest.approx(40.0)


async def test_missing_attempt_dates_fall_back_to_one_day_floor():
    """Missing attempt_date on the graded items floors the span to 1 day."""
    profile_id = uuid4()

    items = [
        _chat(profile_id, grade_score=50, attempt_date=date(2026, 1, 1)),
        _chat(profile_id, grade_score=90, attempt_date=date(2026, 1, 1)),
    ]
    # Strip the dates to exercise the None-date guard path.
    for it in items:
        it.attempt_date = None

    rows = build_leaderboard_rows_v2(items)

    assert _rate(rows, profile_id) == pytest.approx(40.0)
