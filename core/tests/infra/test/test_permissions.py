"""Tests for test permissions — compute_test_status."""

import pytest

from app.infra.test.permissions import compute_test_status

pytestmark = pytest.mark.asyncio


async def test_pending_when_no_chats():
    assert compute_test_status(num_chats=0, num_chats_completed=0) == "pending"
    assert compute_test_status(num_chats=None, num_chats_completed=None) == "pending"


async def test_running_when_none_completed():
    assert compute_test_status(num_chats=5, num_chats_completed=0) == "running"
    assert compute_test_status(num_chats=5, num_chats_completed=None) == "running"


async def test_completed_when_all_done():
    assert compute_test_status(num_chats=5, num_chats_completed=5) == "completed"
    assert compute_test_status(num_chats=5, num_chats_completed=10) == "completed"


async def test_running_when_partially_completed():
    assert compute_test_status(num_chats=5, num_chats_completed=3) == "running"


async def test_negative_total_is_pending():
    assert compute_test_status(num_chats=-1, num_chats_completed=0) == "pending"
