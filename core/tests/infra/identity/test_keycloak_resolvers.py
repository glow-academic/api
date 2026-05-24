"""Tests for keycloak_resolvers — compose canonical black boxes for sync."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.infra.identity.keycloak_resolvers import (
    AuthForSync,
    AuthItem,
    DepartmentForSync,
    SettingProfileForIdp,
    resolve_auths_for_department,
    resolve_departments_for_sync,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


@dataclass
class _FakeDeptResource:
    id: object
    name: str
    setting_ids: list | None = None


@dataclass
class _FakeDeptArtifact:
    settings_ids: list | None = None


@dataclass
class _FakeSettingArtifact:
    auth_ids: list | None = None


@dataclass
class _FakeAuthResource:
    id: object
    slug: str | None
    protocol: str | None
    name: str | None
    active: bool = True


async def test_resolve_departments_for_sync_returns_empty_when_no_depts():
    """Returns empty list when no active departments exist."""
    conn = AsyncMock()
    redis = AsyncMock()

    with patch(
        "app.infra.identity.keycloak_resolvers.search_departments",
        new_callable=AsyncMock,
        return_value=([], 0),
    ):
        result = await resolve_departments_for_sync(conn, redis)

    assert result == []


async def test_resolve_departments_for_sync_returns_mapped_departments():
    """Returns DepartmentForSync entries from active departments."""
    conn = AsyncMock()
    redis = AsyncMock()
    dept_id = uuid4()

    with patch(
        "app.infra.identity.keycloak_resolvers.search_departments",
        new_callable=AsyncMock,
        return_value=([dept_id], 1),
    ):
        with patch(
            "app.infra.identity.keycloak_resolvers.get_department_resources",
            new_callable=AsyncMock,
            return_value=[_FakeDeptResource(id=dept_id, name="Sales")],
        ):
            result = await resolve_departments_for_sync(conn, redis)

    assert len(result) == 1
    assert isinstance(result[0], DepartmentForSync)
    assert result[0].department_id == dept_id
    assert result[0].department_name == "Sales"


async def test_resolve_auths_for_department_returns_empty_when_no_dept_artifact():
    """Returns empty list when department artifact is not found."""
    conn = AsyncMock()
    redis = AsyncMock()

    with patch(
        "app.infra.identity.keycloak_resolvers.get_department_artifacts",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await resolve_auths_for_department(conn, redis, uuid4())

    assert result == []


async def test_resolve_auths_for_department_returns_active_auths():
    """Returns AuthForSync entries from department artifact chain."""
    conn = AsyncMock()
    redis = AsyncMock()
    dept_id = uuid4()
    setting_id = uuid4()
    auth_id = uuid4()

    dept_artifact = _FakeDeptArtifact(settings_ids=[setting_id])
    setting_artifact = _FakeSettingArtifact(auth_ids=[auth_id])
    auth_resource = _FakeAuthResource(
        id=auth_id, slug="google", protocol="oidc", name="Google SSO"
    )

    with patch(
        "app.infra.identity.keycloak_resolvers.get_department_artifacts",
        new_callable=AsyncMock,
        return_value=[dept_artifact],
    ):
        with patch(
            "app.infra.identity.keycloak_resolvers.get_setting_artifacts",
            new_callable=AsyncMock,
            return_value=[setting_artifact],
        ):
            with patch(
                "app.infra.identity.keycloak_resolvers.get_auth_resources",
                new_callable=AsyncMock,
                return_value=[auth_resource],
            ):
                result = await resolve_auths_for_department(conn, redis, dept_id)

    assert len(result) == 1
    assert isinstance(result[0], AuthForSync)
    assert result[0].slug == "google"
    assert result[0].provider_id == "oidc"
    assert result[0].name == "Google SSO"


async def test_resolve_auths_for_department_skips_inactive_auths():
    """Inactive auth resources are excluded from results."""
    conn = AsyncMock()
    redis = AsyncMock()
    dept_id = uuid4()
    setting_id = uuid4()
    auth_id = uuid4()

    dept_artifact = _FakeDeptArtifact(settings_ids=[setting_id])
    setting_artifact = _FakeSettingArtifact(auth_ids=[auth_id])
    inactive_auth = _FakeAuthResource(
        id=auth_id,
        slug="old-provider",
        protocol="saml",
        name="Old Provider",
        active=False,
    )

    with patch(
        "app.infra.identity.keycloak_resolvers.get_department_artifacts",
        new_callable=AsyncMock,
        return_value=[dept_artifact],
    ):
        with patch(
            "app.infra.identity.keycloak_resolvers.get_setting_artifacts",
            new_callable=AsyncMock,
            return_value=[setting_artifact],
        ):
            with patch(
                "app.infra.identity.keycloak_resolvers.get_auth_resources",
                new_callable=AsyncMock,
                return_value=[inactive_auth],
            ):
                result = await resolve_auths_for_department(conn, redis, dept_id)

    assert result == []


async def test_dataclass_fields():
    """Verify dataclass fields are correctly set."""
    dept = DepartmentForSync(department_id=uuid4(), department_name="HR")
    assert dept.department_name == "HR"

    auth = AuthForSync(id=uuid4(), slug="okta", provider_id="oidc", name="Okta")
    assert auth.slug == "okta"

    item = AuthItem(name="client_id", value="abc", encrypted=False)
    assert item.encrypted is False

    profile = SettingProfileForIdp(
        profile_id=uuid4(),
        profile_name="Admin",
        role="admin",
        setting_id=uuid4(),
        department_id=None,
    )
    assert profile.department_id is None
