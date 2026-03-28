"""Tests for attempt permissions — check_attempt_access."""
import pytest
from uuid import uuid4
from app.infra.attempt.permissions import check_attempt_access, ROLE_HIERARCHY
pytestmark = pytest.mark.asyncio

async def test_access_own_attempt():
    pid = uuid4()
    assert check_attempt_access(attempt_profile_id=pid, request_profile_id=pid) is True

async def test_no_access_none_attempt_profile():
    assert check_attempt_access(attempt_profile_id=None, request_profile_id=uuid4()) is False

async def test_higher_role_gets_access():
    assert check_attempt_access(
        attempt_profile_id=uuid4(), request_profile_id=uuid4(),
        request_role="admin", attempt_role="member",
    ) is True

async def test_role_hierarchy_ordering():
    assert ROLE_HIERARCHY["superadmin"] > ROLE_HIERARCHY["admin"]
    assert ROLE_HIERARCHY["admin"] > ROLE_HIERARCHY["instructional"]
    assert ROLE_HIERARCHY["instructional"] > ROLE_HIERARCHY["member"]
