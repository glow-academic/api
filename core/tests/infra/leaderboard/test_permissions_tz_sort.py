"""Regression tests for tz-aware datetime sorting in leaderboard permissions.

api#182 (session timeline) was a real production crash of the form
``TypeError: can't compare offset-naive and offset-aware datetimes`` — a sort
key that fell back to a *naive* ``datetime.min`` while sibling rows carried
*aware* PG ``timestamptz`` values (asyncpg → tz-aware). The same antipattern
lived on in ``leaderboard/permissions.py``:

  - ``compute_message_stats`` sorted ``GetAttemptMessageResponse`` rows by
    ``m.created_at or datetime.min``
  - ``_profile_context`` sorted attempts by ``a.attempt_created_at or datetime.min``

These crash the moment any one row's timestamp is ``None`` while another row
in the same group is aware. These tests reproduce the crash shape on the real
``GetAttemptMessageResponse`` model and prove the fix sorts cleanly + correctly.

Modular: deps (the message rows) are passed in explicitly; no DB/Redis.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.infra.leaderboard.permissions import (
    _dt_sort_key,
    compute_message_stats,
)
from app.tools.entries.attempt_message.types import GetAttemptMessageResponse

pytestmark = pytest.mark.asyncio


def _msg(
    chat_id,
    msg_type: str,
    created_at: datetime | None,
) -> GetAttemptMessageResponse:
    """Build a real GetAttemptMessageResponse row (factory; aware unless given)."""
    return GetAttemptMessageResponse(
        message_id=uuid4(),
        chat_id=chat_id,
        attempt_id=uuid4(),
        type=msg_type,
        created_at=created_at,
        completed=True,
        text_id=None,
        history_file_path=None,
        audios_id=None,
    )


async def test_compute_message_stats_mixed_none_and_aware_does_not_crash():
    """A None created_at alongside aware (timestamptz) siblings must not raise.

    Before the fix, ``sorted(..., key=lambda m: m.created_at or datetime.min)``
    raised ``TypeError: can't compare offset-naive and offset-aware datetimes``
    because ``datetime.min`` is naive while the other rows are aware-UTC.
    """
    chat_id = uuid4()
    aware = datetime(2026, 6, 6, 12, 0, 0, tzinfo=timezone.utc)
    msgs = [
        _msg(chat_id, "query", aware),
        _msg(chat_id, "response", None),  # None → naive sentinel pre-fix
        _msg(chat_id, "response", aware.replace(minute=5)),
    ]

    # Must not raise TypeError.
    stats = compute_message_stats(msgs)

    assert chat_id in stats
    assert stats[chat_id]["num_messages_total"] == 3


async def test_compute_message_stats_orders_by_aware_created_at():
    """With all-aware rows the response-time delta is computed correctly."""
    chat_id = uuid4()
    base = datetime(2026, 6, 6, 12, 0, 0, tzinfo=timezone.utc)
    # Build out of chronological order to exercise the sort.
    msgs = [
        _msg(chat_id, "response", base.replace(second=30)),  # +30s after query
        _msg(chat_id, "query", base),
    ]

    stats = compute_message_stats(msgs)

    # query→response pair, 30 seconds apart.
    assert stats[chat_id]["avg_response_sec"] == 30.0


async def test_dt_sort_key_normalizes_none_and_naive_to_aware():
    """The sort-key helper yields only aware-UTC values (never naive)."""
    aware = datetime(2026, 6, 6, tzinfo=timezone.utc)
    naive = datetime(2026, 6, 6)

    none_key = _dt_sort_key(None)
    naive_key = _dt_sort_key(naive)
    aware_key = _dt_sort_key(aware)

    assert none_key.tzinfo is not None
    assert naive_key.tzinfo is not None
    assert aware_key is aware  # already aware → returned unchanged

    # The whole point: these are now mutually comparable (no TypeError).
    assert aware_key < none_key
    assert naive_key.replace(tzinfo=timezone.utc) == naive_key
