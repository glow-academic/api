"""Tests for profile permissions — compute_can_edit."""
import pytest
from app.infra.profile.permissions import compute_can_edit
pytestmark = pytest.mark.asyncio

async def test_can_edit_self():
    assert compute_can_edit(user_role="member", target_is_self=True, target_department_ids=[]) is True

async def test_superadmin_can_edit_all():
    assert compute_can_edit(user_role="superadmin", target_is_self=False, target_department_ids=[]) is True

async def test_member_cannot_edit_others():
    assert compute_can_edit(user_role="member", target_is_self=False, target_department_ids=[]) is False
