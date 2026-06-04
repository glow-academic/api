"""Tests for _build_timeline sort robustness against None / mixed-tz created_at.

_build_timeline merges heterogeneous timeline sources (typed MV rows + raw
chat_mv dicts) into one list sorted by created_at. The sort key must tolerate:
  - a missing/NULL created_at (None) -> previously raised TypeError comparing
    NoneType vs datetime,
  - a naive datetime mixed with aware ones -> previously raised
    "can't compare offset-naive and offset-aware datetimes".

These are pure-function tests with no DB; data is constructed directly.
"""
from datetime import datetime, timezone

from app.infra.session.get import _build_timeline
from app.infra.session.types import SessionInternalData


def _problem(created_at):
    return type(
        "P",
        (),
        {"id": None, "type": "t", "created_at": created_at, "message": "m"},
    )()


def test_build_timeline_handles_none_created_at():
    """A chat dict with created_at=None must not crash the sort (NULLS LAST)."""
    data = SessionInternalData(
        chats=[{"chat_entry_id": None, "name": "c1", "created_at": None}],
        problems=[_problem(datetime(2026, 1, 1, tzinfo=timezone.utc))],
    )
    timeline = _build_timeline(data)
    assert len(timeline) == 2
    # The real (non-None) event sorts before the None one.
    assert timeline[0].event_type == "problem"
    assert timeline[1].created_at is None


def test_build_timeline_handles_mixed_naive_and_aware():
    """Naive and aware datetimes across sources must not crash the sort."""
    data = SessionInternalData(
        chats=[{"chat_entry_id": None, "name": "c", "created_at": datetime(2026, 1, 2)}],
        problems=[_problem(datetime(2026, 1, 1, tzinfo=timezone.utc))],
    )
    timeline = _build_timeline(data)
    assert len(timeline) == 2
    # 2026-01-01 (aware) < 2026-01-02 (naive treated as UTC).
    assert timeline[0].event_type == "problem"
    assert timeline[1].event_type == "chat"


def test_build_timeline_orders_multiple_sources_ascending():
    """Well-formed aware timestamps sort ascending across source types."""
    data = SessionInternalData(
        chats=[
            {"chat_entry_id": None, "name": "c", "created_at": datetime(2026, 3, 1, tzinfo=timezone.utc)}
        ],
        problems=[_problem(datetime(2026, 1, 1, tzinfo=timezone.utc))],
        practices=[
            type("Pr", (), {"id": None, "created_at": datetime(2026, 2, 1, tzinfo=timezone.utc)})()
        ],
    )
    timeline = _build_timeline(data)
    assert [i.event_type for i in timeline] == ["problem", "practice", "chat"]
