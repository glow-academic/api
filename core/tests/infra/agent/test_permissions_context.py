"""Tests for agent permissions context + shared save helpers."""

from dataclasses import dataclass
from uuid import uuid4

import pytest

from app.infra.agent.permissions_context import (
    AgentPermissionsContext,
    resolve_agent_permissions_context,
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
        "app.infra.agent.permissions_context.get_agent_artifacts",
        mock_get,
    )

    result = await resolve_agent_permissions_context(None, uuid4())
    assert result.exists is False
    assert result.department_ids == []


async def test_resolve_returns_exists_with_departments(monkeypatch):
    dept_id = uuid4()
    artifact = _FakeArtifact(id=uuid4(), department_ids=[dept_id])

    async def mock_get(conn, ids, **kw):
        return [artifact]

    monkeypatch.setattr(
        "app.infra.agent.permissions_context.get_agent_artifacts",
        mock_get,
    )

    result = await resolve_agent_permissions_context(None, artifact.id)
    assert result.exists is True
    assert dept_id in result.department_ids


async def test_resolve_handles_none_departments(monkeypatch):
    artifact = _FakeArtifact(id=uuid4(), department_ids=None)

    async def mock_get(conn, ids, **kw):
        return [artifact]

    monkeypatch.setattr(
        "app.infra.agent.permissions_context.get_agent_artifacts",
        mock_get,
    )

    result = await resolve_agent_permissions_context(None, artifact.id)
    assert result.exists is True
    assert result.department_ids == []


async def test_agent_permissions_context_is_frozen():
    ctx = AgentPermissionsContext(exists=True, department_ids=[])
    with pytest.raises(AttributeError):
        ctx.exists = False
