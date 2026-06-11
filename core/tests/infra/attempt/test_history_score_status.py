"""Regression tests for history score_status pass-bar (B3).

`build_history_response` computed `score_status` against a hardcoded
`pass_threshold = 70.0` while the per-item `pass_pct` it returned in the same
response was derived from the rubric's `pass_points` / `total_points`. So the
same attempt could show a rubric-based pass_pct of 60 yet a score_status that
treated 70 as the bar — the two fields disagreed for the same grade.

The fix derives the threshold from the rubric (compute_pass_pct) per item,
mirroring benchmark/get.py, falling back to the supplied default only when the
attempt has no rubric points.

Modular: `_transform_history_item` is exercised directly with a SimpleNamespace
attempt + an aggregates dict carrying the rubric points. No DB/Redis/MV.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.infra.attempt.history import _transform_history_item

pytestmark = pytest.mark.asyncio


def _attempt() -> SimpleNamespace:
    return SimpleNamespace(
        attempt_id=uuid4(),
        attempt_created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        profile_id=uuid4(),
        simulation_id=uuid4(),
        scenario_ids=None,
        infinite_mode=False,
        department_id=None,
        is_archived=False,
    )


_EMPTY_META = {
    "simulations": {},
    "profiles": {},
    "personas": {},
    "scenarios": {},
}


def _transform(*, score_percent, pass_points, total_points):
    aggregates = {
        "score_percent": score_percent,
        "rubric_total_points": total_points,
        "rubric_pass_points": pass_points,
        "num_chats": 1,
        "num_chats_completed": 1,
        "num_scenarios": 1,
        "num_scenarios_completed": 1,
        "total_time_seconds": 0,
        "persona_ids": None,
        "scenario_ids": None,
    }
    return _transform_history_item(
        _attempt(), aggregates, _EMPTY_META, 70.0, practice=False
    )


async def test_score_status_uses_rubric_pass_bar_not_70():
    """65% with a 60% rubric bar is a pass ('high'), not 'medium' under 70."""
    item = _transform(score_percent=65.0, pass_points=60, total_points=100)
    # pass_pct reflects the rubric (60), and score_status must agree with it.
    assert item.pass_pct == 60
    assert item.score_status == "high"


async def test_score_status_below_rubric_bar_is_not_high():
    """55% with a 60% rubric bar is below the bar → not 'high'."""
    item = _transform(score_percent=55.0, pass_points=60, total_points=100)
    assert item.pass_pct == 60
    assert item.score_status == "medium"  # >= 40 but < 60


async def test_score_status_falls_back_to_default_without_rubric():
    """No rubric points → fall back to the supplied 70 default."""
    item = _transform(score_percent=65.0, pass_points=None, total_points=None)
    assert item.pass_pct is None
    # 65 < 70 default → not 'high'.
    assert item.score_status == "medium"
