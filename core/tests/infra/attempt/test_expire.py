"""Tests for the auto-expire background job (``app.infra.attempt.expire``).

Regression coverage for the live-QA bug where the expire loop error-loops
forever on stale attempts whose owner profile is unresolvable.

``complete_attempt_impl`` writes the attempt's completion (terminal) row first,
then runs a profile-scoped MV refresh. For a "bare-shell" owner (active
``profiles_resource`` row but 0 active role/email/name junctions) the refresh's
permission gate raises ``HTTPException(401, "Profile not found...")``. The old
loop caught it, logged ERROR, and — because the global ``attempt_mv`` never got
refreshed — re-found the same attempt every ``CHECK_INTERVAL`` (60s) forever
(~540 ERROR/hr observed in prod).

The fix degrades gracefully: the attempt is already terminal, so the loop skips
the (meaningless) profile-scoped refresh and enqueues the same MVs directly so
the attempt is NOT reprocessed next cycle. Normal (resolvable) owners still
expire + refresh exactly as before.

Deps are injected as explicit params (pool/redis are mocks; the black-box
search/complete/enqueue calls are monkeypatched module attrs).
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.asyncio


def _fake_pool() -> MagicMock:
    """Pool whose ``acquire()`` is an async-context-manager yielding a conn.

    ``acquire`` is a plain (sync) MagicMock so ``pool.acquire()`` returns the
    context manager directly (not a coroutine); the yielded conn is unused
    because every black-box DB call in the loop is monkeypatched.
    """
    pool = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = cm
    return pool


def _stale_attempt(profile_id: UUID | None) -> SimpleNamespace:
    return SimpleNamespace(attempt_id=uuid4(), profile_id=profile_id)


def _stale_chat() -> SimpleNamespace:
    # created well past time_limit + grace so the attempt is stale.
    return SimpleNamespace(
        chat_created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        time_limit_seconds=60,
    )


def _wire_searches(monkeypatch, m, attempts):
    monkeypatch.setattr(
        m, "search_attempts", AsyncMock(return_value=(attempts, len(attempts)))
    )
    monkeypatch.setattr(
        m, "search_attempt_chats", AsyncMock(return_value=([_stale_chat()], 1))
    )


async def test_unresolvable_owner_expires_gracefully_without_raise_or_error(
    monkeypatch, caplog
):
    """Stale attempt with an unresolvable owner: handled gracefully.

    - does NOT raise
    - is treated as expired (so NOT re-found next cycle)
    - enqueues the MV refresh directly so ``attempt_mv`` flips
    - logs no ERROR (benign WARNING only)
    """
    import logging

    import app.infra.attempt.expire as m

    bad_owner = uuid4()
    _wire_searches(monkeypatch, m, [_stale_attempt(bad_owner)])

    # complete writes the terminal row, then the profile-scoped refresh 401s.
    monkeypatch.setattr(
        m,
        "complete_attempt_impl",
        AsyncMock(
            side_effect=HTTPException(
                status_code=401, detail="Profile not found. Please sign in again."
            )
        ),
    )
    enqueue = AsyncMock()
    monkeypatch.setattr(m, "enqueue_pending", enqueue)

    pool, redis = _fake_pool(), AsyncMock()

    with caplog.at_level(logging.WARNING):
        expired = await m.expire_stale_attempts(pool, redis)

    # Treated as expired → will NOT be reprocessed next cycle.
    assert len(expired) == 1
    # MV refresh enqueued directly (degraded, owner-less) so attempt_mv flips.
    assert enqueue.await_count == len(m._COMPLETE_REFRESH_TARGETS)
    enqueued_targets = {c.args[1] for c in enqueue.await_args_list}
    assert enqueued_targets == set(m._COMPLETE_REFRESH_TARGETS)
    # No ERROR spam.
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


async def test_resolvable_owner_still_expires_and_refreshes(monkeypatch):
    """Normal attempt with a resolvable owner expires + refreshes as before."""
    import app.infra.attempt.expire as m

    _wire_searches(monkeypatch, m, [_stale_attempt(uuid4())])

    completion_id = str(uuid4())
    complete = AsyncMock(
        return_value={"success": True, "completion_id": completion_id}
    )
    monkeypatch.setattr(m, "complete_attempt_impl", complete)
    # complete_attempt_impl owns the refresh on the happy path; the degraded
    # direct-enqueue must NOT fire here.
    enqueue = AsyncMock()
    monkeypatch.setattr(m, "enqueue_pending", enqueue)

    pool, redis = _fake_pool(), AsyncMock()
    expired = await m.expire_stale_attempts(pool, redis)

    assert len(expired) == 1
    assert expired[0]["completion_id"] == completion_id
    complete.assert_awaited_once()
    enqueue.assert_not_awaited()


async def test_non_401_http_error_still_surfaces_as_error(monkeypatch, caplog):
    """A genuine (non-401) failure is NOT swallowed — still logs ERROR.

    Guards against the fix broadly papering over real errors.
    """
    import logging

    import app.infra.attempt.expire as m

    _wire_searches(monkeypatch, m, [_stale_attempt(uuid4())])
    monkeypatch.setattr(
        m,
        "complete_attempt_impl",
        AsyncMock(side_effect=HTTPException(status_code=500, detail="boom")),
    )
    enqueue = AsyncMock()
    monkeypatch.setattr(m, "enqueue_pending", enqueue)

    pool, redis = _fake_pool(), AsyncMock()
    with caplog.at_level(logging.ERROR):
        expired = await m.expire_stale_attempts(pool, redis)

    assert expired == []  # NOT treated as expired → not silently dropped
    enqueue.assert_not_awaited()  # no degraded enqueue for non-401
    assert [r for r in caplog.records if r.levelno >= logging.ERROR]
