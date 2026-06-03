"""Tests for permissions — re-exports from auth.route_permissions."""
import pytest
from app.infra.permissions import ROUTE_PERMISSIONS, ProfileRole, RoutePermission, SectionPermission
pytestmark = pytest.mark.asyncio

async def test_route_permissions_is_list_of_sections():
    # ROUTE_PERMISSIONS is a list[SectionPermission] (was previously a dict).
    assert isinstance(ROUTE_PERMISSIONS, list)
    assert len(ROUTE_PERMISSIONS) > 0
    assert all(isinstance(sp, SectionPermission) for sp in ROUTE_PERMISSIONS)

async def test_profile_role_exists():
    assert ProfileRole is not None

async def test_route_permission_exists():
    assert RoutePermission is not None

async def test_section_permission_exists():
    assert SectionPermission is not None
