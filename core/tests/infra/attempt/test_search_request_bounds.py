"""Tests for SearchAttemptApiRequest pagination bounds (B1 DoS guard).

The WS ``attempt.search`` handler (core/app/ws/attempt/search.py) deserializes
the socket payload into the *infra* ``SearchAttemptApiRequest`` and passes
``page_size`` straight into ``search_attempt_impl`` ->
``resolve_dashboard_search_context(limit=page_size)`` -> ``search_attempts``,
whose SQL sink is ``LIMIT (limit + offset + 1000)`` with no clamp. Before the
fix this model had ``page_size: int = 20`` (no upper bound), so a socket caller
could request ``page_size=100_000_000`` and force an unbounded scan + in-memory
row materialization (OOM / box-hang) — the HTTP route was already capped
(le=200) but the socket path bypassed it.

These tests pin the bound at the model boundary so the WS path can no longer
request an unbounded LIMIT.
"""

import pytest
from pydantic import ValidationError

from app.infra.attempt.types import SearchAttemptApiRequest


def test_default_page_size_unchanged():
    assert SearchAttemptApiRequest().page_size == 20


def test_page_size_within_bound_is_accepted():
    req = SearchAttemptApiRequest(page_size=200)
    assert req.page_size == 200


def test_page_size_above_max_is_rejected():
    # Pathological full-table pull must not validate (the WS handler treats a
    # ValidationError as attempt.search.failed → no query runs).
    with pytest.raises(ValidationError):
        SearchAttemptApiRequest(page_size=100_000_000)


def test_page_size_just_above_max_is_rejected():
    with pytest.raises(ValidationError):
        SearchAttemptApiRequest(page_size=201)


def test_page_size_zero_is_rejected():
    with pytest.raises(ValidationError):
        SearchAttemptApiRequest(page_size=0)
