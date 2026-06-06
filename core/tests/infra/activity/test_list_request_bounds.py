"""Tests for ListActivityRequest pagination bounds (DoS guard).

``page_size`` flows straight into ``search_sessions(limit=page_size)`` -> SQL
``LIMIT $n``. Without a server-side cap an authenticated caller could request
an arbitrarily large page (e.g. 100_000_000) and force a full-table load of
``sessions_mv`` into memory. These tests pin the bound at the model boundary
(enforced for both the HTTP ``POST /system/sessions`` route and the
``system.activity_search`` socket path, which both construct this model).
"""

import pytest
from pydantic import ValidationError

from app.infra.activity.types import ListActivityRequest


def test_page_size_within_bound_is_accepted():
    req = ListActivityRequest(page_size=200)
    assert req.page_size == 200


def test_page_size_default_is_unchanged():
    assert ListActivityRequest().page_size == 50


def test_page_size_above_max_is_rejected():
    # Pathological full-table pull must not validate.
    with pytest.raises(ValidationError):
        ListActivityRequest(page_size=100_000_000)


def test_page_size_just_above_max_is_rejected():
    with pytest.raises(ValidationError):
        ListActivityRequest(page_size=201)


def test_page_size_zero_is_rejected():
    # page_size == 0 would also break total_pages math; require >= 1.
    with pytest.raises(ValidationError):
        ListActivityRequest(page_size=0)


def test_negative_page_is_rejected():
    # Negative page => negative OFFSET; disallow.
    with pytest.raises(ValidationError):
        ListActivityRequest(page=-1)
