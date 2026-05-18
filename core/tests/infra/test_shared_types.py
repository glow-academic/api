"""Tests for shared_types — Pydantic model definitions."""
import pytest
from app.infra.shared_types import (
    QGetProfileContextV4RoleResource,
    QGetProfileContextV4Department,
    QGetSettingsV4Item,
    QGetAgentsV4Item,
    QGetModelsV4Item,
    QGetToolsV4Item,
    GetProfileContextApiRequest,
)
pytestmark = pytest.mark.asyncio

async def test_role_resource_defaults():
    r = QGetProfileContextV4RoleResource()
    assert r.role is None
    assert r.name is None

async def test_department_defaults():
    d = QGetProfileContextV4Department()
    assert d.department_id is None
    assert d.active is None

async def test_settings_item_defaults():
    s = QGetSettingsV4Item()
    assert s.settings_id is None

async def test_agents_item_defaults():
    a = QGetAgentsV4Item()
    assert a.id is None
    assert a.tool_ids is None

async def test_profile_context_request():
    r = GetProfileContextApiRequest()
    assert r.department_id is None
