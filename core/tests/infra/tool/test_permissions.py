"""Tests for tool permissions — compute_can_edit, compute_disabled_reason."""
import pytest
from app.infra.tool.permissions import compute_can_edit, compute_disabled_reason
pytestmark = pytest.mark.asyncio

_TOOL_UPDATE = [("tool", "update")]
_NO_PERMS = []

async def test_can_edit_false_when_agents_active():
    assert compute_can_edit(role_level=1, role_permissions=_TOOL_UPDATE, active_agent_count=1) is False

async def test_can_edit_true_for_admin_no_agents():
    assert compute_can_edit(role_level=1, role_permissions=_TOOL_UPDATE, active_agent_count=0) is True

async def test_can_edit_false_for_member():
    assert compute_can_edit(role_level=3, role_permissions=_NO_PERMS, active_agent_count=0) is False

async def test_disabled_reason_active_agents():
    reason = compute_disabled_reason(role_permissions=_TOOL_UPDATE, active_agent_count=1)
    assert reason is not None
    assert "agents" in reason.lower()

async def test_disabled_reason_none_when_can_edit():
    reason = compute_disabled_reason(role_permissions=_TOOL_UPDATE, active_agent_count=0)
    assert reason is None
