"""Tests for profile permissions — compute_can_edit."""
import pytest
from app.infra.profile.permissions import compute_can_edit
pytestmark = pytest.mark.asyncio

_PROFILE_UPDATE = [("profile", "update")]
_NO_PERMS = []

async def test_can_edit_self():
    assert compute_can_edit(role_level=3, role_permissions=_NO_PERMS, target_is_self=True, target_department_ids=[]) is True

async def test_superadmin_can_edit_all():
    assert compute_can_edit(role_level=0, role_permissions=_PROFILE_UPDATE, target_is_self=False, target_department_ids=[]) is True

async def test_member_cannot_edit_others():
    assert compute_can_edit(role_level=3, role_permissions=_NO_PERMS, target_is_self=False, target_department_ids=[]) is False
