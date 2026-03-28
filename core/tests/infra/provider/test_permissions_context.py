"""Tests for provider permissions context + shared save helpers."""

from dataclasses import dataclass
from uuid import uuid4

import pytest

from app.infra.provider.permissions_context import (
    ProviderPermissionsContext,
    resolve_provider_permissions_context,
)

pytestmark = pytest.mark.asyncio


@dataclass
class _FakeArtifact:
    id: object
    department_ids: list | None = None


async def test_resolve_returns_not_exists_for_missing_artifact(monkeypatch):
    async def mock_get(conn, ids, **kw):
        return []

    monkeypatch.setattr(
        "app.infra.provider.permissions_context.get_provider_artifacts",
        mock_get,
    )

    result = await resolve_provider_permissions_context(None, uuid4())
    assert result.exists is False
    assert result.department_ids == []
    assert result.active_model_count == 0


async def test_resolve_returns_exists_with_departments(monkeypatch):
    dept_id = uuid4()
    artifact = _FakeArtifact(id=uuid4(), department_ids=[dept_id])

    async def mock_get(conn, ids, **kw):
        return [artifact]

    async def mock_search_models(conn, provider_ids=None, active_only=True, limit_count=1):
        return ([], 0)

    monkeypatch.setattr(
        "app.infra.provider.permissions_context.get_provider_artifacts",
        mock_get,
    )
    monkeypatch.setattr(
        "app.infra.provider.permissions_context.search_models",
        mock_search_models,
    )

    result = await resolve_provider_permissions_context(None, artifact.id)
    assert result.exists is True
    assert dept_id in result.department_ids


async def test_resolve_counts_active_models(monkeypatch):
    artifact = _FakeArtifact(id=uuid4(), department_ids=[])

    async def mock_get(conn, ids, **kw):
        return [artifact]

    async def mock_search_models(conn, provider_ids=None, active_only=True, limit_count=1):
        return ([], 5)

    monkeypatch.setattr(
        "app.infra.provider.permissions_context.get_provider_artifacts",
        mock_get,
    )
    monkeypatch.setattr(
        "app.infra.provider.permissions_context.search_models",
        mock_search_models,
    )

    result = await resolve_provider_permissions_context(None, artifact.id)
    assert result.active_model_count == 5


async def test_provider_permissions_context_is_frozen():
    ctx = ProviderPermissionsContext(exists=True, department_ids=[], active_model_count=0)
    with pytest.raises(AttributeError):
        ctx.exists = False
