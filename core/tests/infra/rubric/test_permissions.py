"""Tests for rubric permissions — compute_can_edit."""
import pytest
from app.infra.rubric.permissions import compute_can_edit, compute_disabled_reason
pytestmark = pytest.mark.asyncio(loop_scope="session")

_RUBRIC_UPDATE = [("rubric", "update")]
_NO_PERMS = []

async def test_can_edit_superadmin():
    assert compute_can_edit(role_level=0, role_permissions=_RUBRIC_UPDATE, rubric_department_ids=["d1"], active_simulation_count=0) is True

async def test_cannot_edit_with_active_simulations():
    assert compute_can_edit(role_level=0, role_permissions=_RUBRIC_UPDATE, rubric_department_ids=["d1"], active_simulation_count=1) is False

async def test_cannot_edit_default_rubric_non_superadmin():
    assert compute_can_edit(role_level=1, role_permissions=_RUBRIC_UPDATE, rubric_department_ids=None, active_simulation_count=0) is False

async def test_disabled_reason_active_sims():
    reason = compute_disabled_reason(role_level=0, role_permissions=_RUBRIC_UPDATE, rubric_department_ids=["d1"], active_simulation_count=1)
    assert reason is not None
