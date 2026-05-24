"""Tests for simulation permissions context + shared save helpers."""

from dataclasses import dataclass
from uuid import uuid4

import pytest

from app.infra.simulation.permissions_context import (
    SimulationPermissionsContext,
    resolve_simulation_permissions_context,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


@dataclass
class _FakeArtifact:
    id: object
    department_ids: list | None = None
    simulation_ids: list | None = None


async def test_resolve_returns_not_exists_for_missing_artifact(monkeypatch):
    async def mock_get(conn, ids, **kw):
        return []

    monkeypatch.setattr(
        "app.infra.simulation.permissions_context.get_simulation_artifacts",
        mock_get,
    )

    result = await resolve_simulation_permissions_context(None, uuid4())
    assert result.exists is False
    assert result.department_ids == []
    assert result.cohort_usage_count == 0


async def test_resolve_returns_exists_with_departments(monkeypatch):
    dept_id = uuid4()
    artifact = _FakeArtifact(
        id=uuid4(), department_ids=[dept_id], simulation_ids=[]
    )

    async def mock_get(conn, ids, **kw):
        return [artifact]

    monkeypatch.setattr(
        "app.infra.simulation.permissions_context.get_simulation_artifacts",
        mock_get,
    )

    result = await resolve_simulation_permissions_context(None, artifact.id)
    assert result.exists is True
    assert dept_id in result.department_ids
    assert result.cohort_usage_count == 0


async def test_resolve_counts_cohort_usage(monkeypatch):
    sim_resource_id = uuid4()
    artifact = _FakeArtifact(
        id=uuid4(), department_ids=[], simulation_ids=[sim_resource_id]
    )

    async def mock_get(conn, ids, **kw):
        return [artifact]

    async def mock_search_cohorts(conn, simulation_ids=None, active_only=True, limit_count=1):
        return ([], 7)

    monkeypatch.setattr(
        "app.infra.simulation.permissions_context.get_simulation_artifacts",
        mock_get,
    )
    monkeypatch.setattr(
        "app.infra.simulation.permissions_context.search_cohorts",
        mock_search_cohorts,
    )

    result = await resolve_simulation_permissions_context(None, artifact.id)
    assert result.cohort_usage_count == 7


async def test_simulation_permissions_context_is_frozen():
    ctx = SimulationPermissionsContext(
        exists=True, department_ids=[], cohort_usage_count=0
    )
    with pytest.raises(AttributeError):
        ctx.exists = False
