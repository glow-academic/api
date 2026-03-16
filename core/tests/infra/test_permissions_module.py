"""Tests for infra.permissions re-exports."""

from app.infra.permissions import (
    ROUTE_PERMISSIONS,
    ProfileRole,
    RoutePermission,
    SectionPermission,
)
from app.infra.auth.route_permissions import (
    ROUTE_PERMISSIONS as CANONICAL_ROUTE_PERMISSIONS,
)
from app.infra.auth.route_permissions import (
    ProfileRole as CanonicalProfileRole,
)
from app.infra.auth.route_permissions import (
    RoutePermission as CanonicalRoutePermission,
)
from app.infra.auth.route_permissions import (
    SectionPermission as CanonicalSectionPermission,
)


def test_reexports_canonical_objects():
    assert ROUTE_PERMISSIONS is CANONICAL_ROUTE_PERMISSIONS
    assert ProfileRole is CanonicalProfileRole
    assert RoutePermission is CanonicalRoutePermission
    assert SectionPermission is CanonicalSectionPermission


def test_route_permissions_is_not_empty():
    assert ROUTE_PERMISSIONS
