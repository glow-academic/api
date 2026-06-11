"""Regression tests for the "Perfect Score" / "The Persistent" accolades (B2).

Both accolades were picked with ``_pick_max`` over a count metric
(``perfect_score_count`` / ``total_attempts``). When nobody qualifies, every
row's metric is 0 and ``_pick_max`` still returns a row (max-of-all-zeros), so
``_winner`` awarded the accolade on a zero predicate — a "Perfect Score" with
0 perfect scores, "The Persistent" with 0 attempts.

The fix routes both through ``_pick_max_positive`` (mirrors the existing
``_pick_min_positive`` `> 0` gate) so the accolade is only awarded when at
least one profile has real qualifying data.

Also covers B4: ``ChatItem.grade_percent`` clamps a bonus-inflated raw score
(score > total_points) to 100, matching the benchmark percent path
(``benchmark/get.py:_score_percent``), so the same grade never reports >100%.

Modular: ChatItems are built in-process and passed straight into
``build_leaderboard_rows_v2`` / ``compute_accolade_winners``. No DB/Redis/MV.
"""

from datetime import date, datetime, timezone
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
    grade_total_points: int = 100,
    attempt_id=None,
    attempt_date: date | None = None,
) -> ChatItem:
    d = attempt_date or date(2026, 1, 1)
    return ChatItem(
        chat_id=uuid4(),
        attempt_id=attempt_id or uuid4(),
        profile_id=profile_id,
        grade_score=grade_score,
        grade_total_points=grade_total_points,
        chat_created_at=datetime(d.year, d.month, d.day, tzinfo=timezone.utc),
        attempt_date=d,
    )


# --- B4: ChatItem.grade_percent clamping -----------------------------------


def test_grade_percent_clamped_to_100_on_bonus_inflation():
    """A raw score above total_points reports 100, not >100 (matches benchmark)."""
    inflated = _chat(uuid4(), grade_score=120, grade_total_points=100)
    assert inflated.grade_percent == 100.0
    # Sub-100 grade is unaffected.
    normal = _chat(uuid4(), grade_score=65, grade_total_points=100)
    assert normal.grade_percent == 65.0


# --- B2: Perfect Score accolade --------------------------------------------


async def test_no_perfect_score_when_nobody_scored_100():
    """All profiles below 100 → no "Perfect Score" winner (was awarded on 0)."""
    a, b = uuid4(), uuid4()
    items = [
        _chat(a, grade_score=80),
        _chat(b, grade_score=90),
    ]
    winners = compute_accolade_winners(build_leaderboard_rows_v2(items))
    assert winners.perfect_score is None


async def test_perfect_score_awarded_on_real_100():
    """A profile with an actual 100% graded attempt wins "Perfect Score"."""
    a, b = uuid4(), uuid4()
    items = [
        _chat(a, grade_score=100),  # one real perfect score
        _chat(b, grade_score=90),
    ]
    winners = compute_accolade_winners(build_leaderboard_rows_v2(items))
    assert winners.perfect_score is not None
    assert winners.perfect_score.profile_id == str(a)
    assert winners.perfect_score.value == 1


# --- B2: The Persistent accolade -------------------------------------------


async def test_no_persistent_when_no_attempts():
    """No graded chats at all → no rows → no "The Persistent" winner."""
    winners = compute_accolade_winners(build_leaderboard_rows_v2([]))
    assert winners.the_persistent is None


async def test_persistent_awarded_to_most_attempts():
    """Profile with the most distinct attempts wins "The Persistent" (>0)."""
    a, b = uuid4(), uuid4()
    a1, a2, a3 = uuid4(), uuid4(), uuid4()
    items = [
        _chat(a, grade_score=70, attempt_id=a1),
        _chat(a, grade_score=70, attempt_id=a2),
        _chat(a, grade_score=70, attempt_id=a3),
        _chat(b, grade_score=70, attempt_id=uuid4()),
    ]
    winners = compute_accolade_winners(build_leaderboard_rows_v2(items))
    assert winners.the_persistent is not None
    assert winners.the_persistent.profile_id == str(a)
    assert winners.the_persistent.value == 3
