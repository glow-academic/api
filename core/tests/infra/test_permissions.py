"""Tests for permissions — re-exports from auth.route_permissions."""
import pytest
from app.infra.permissions import ROUTE_PERMISSIONS, ProfileRole, RoutePermission, SectionPermission
pytestmark = pytest.mark.asyncio

async def test_route_permissions_is_dict():
    assert isinstance(ROUTE_PERMISSIONS, dict)
    assert len(ROUTE_PERMISSIONS) > 0

async def test_profile_role_exists():
    assert ProfileRole is not None

async def test_route_permission_exists():
    assert RoutePermission is not None

async def test_section_permission_exists():
    assert SectionPermission is not None
