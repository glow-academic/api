"""Tests for auth permissions context + shared save helpers."""

from dataclasses import dataclass
from uuid import uuid4

import pytest

from app.infra.auth.permissions_context import (
    AuthPermissionsContext,
    resolve_auth_permissions_context,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


@dataclass
class _FakeArtifact:
    id: object
    department_ids: list | None = None
    auth_ids: list | None = None


async def test_resolve_returns_not_exists_for_missing_artifact(monkeypatch):
    async def mock_get_auth_artifacts(conn, ids, **kw):
        return []

    monkeypatch.setattr(
        "app.infra.auth.permissions_context.get_auth_artifacts",
        mock_get_auth_artifacts,
    )

    result = await resolve_auth_permissions_context(None, uuid4())
    assert result.exists is False
    assert result.department_ids == []
    assert result.active_settings_count == 0


async def test_resolve_returns_exists_with_departments(monkeypatch):
    dept_id = uuid4()
    artifact = _FakeArtifact(id=uuid4(), department_ids=[dept_id], auth_ids=[])

    async def mock_get(conn, ids, **kw):
        return [artifact]

    monkeypatch.setattr(
        "app.infra.auth.permissions_context.get_auth_artifacts",
        mock_get,
    )

    result = await resolve_auth_permissions_context(None, artifact.id)
    assert result.exists is True
    assert dept_id in result.department_ids
    assert result.active_settings_count == 0


async def test_resolve_counts_active_settings(monkeypatch):
    auth_resource_id = uuid4()
    artifact = _FakeArtifact(
        id=uuid4(), department_ids=[], auth_ids=[auth_resource_id]
    )

    async def mock_get(conn, ids, **kw):
        return [artifact]

    async def mock_search_settings(conn, auth_ids=None, active_only=True, limit_count=1):
        return ([], 3)

    monkeypatch.setattr(
        "app.infra.auth.permissions_context.get_auth_artifacts",
        mock_get,
    )
    monkeypatch.setattr(
        "app.infra.auth.permissions_context.search_setting_artifacts",
        mock_search_settings,
    )

    result = await resolve_auth_permissions_context(None, artifact.id)
    assert result.exists is True
    assert result.active_settings_count == 3


async def test_auth_permissions_context_is_frozen():
    ctx = AuthPermissionsContext(exists=True, department_ids=[], active_settings_count=0)
    with pytest.raises(AttributeError):
        ctx.exists = False
