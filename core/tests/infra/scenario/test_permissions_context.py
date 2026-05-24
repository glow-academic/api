"""Tests for scenario permissions context — monkeypatch DB tool calls."""

from uuid import uuid4

import pytest

from app.infra.scenario.permissions_context import (
    ScenarioPermissionsContext,
    resolve_scenario_permissions_context,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestPermissionsContextNotFound:
    async def test_returns_not_exists_when_artifact_missing(self, monkeypatch):
        async def fake_get(conn, ids, **kw):
            return []

        monkeypatch.setattr(
            "app.infra.scenario.permissions_context.get_scenario_artifacts",
            fake_get,
        )

        result = await resolve_scenario_permissions_context(object(), uuid4())
        assert result.exists is False
        assert result.department_ids == []
        assert result.active_simulation_count == 0


class TestPermissionsContextDataclass:
    async def test_fields_present(self):
        ctx = ScenarioPermissionsContext(
            exists=True, department_ids=[uuid4()], active_simulation_count=0,
        )
        assert ctx.exists is True
        assert len(ctx.department_ids) == 1
        assert ctx.active_simulation_count == 0

    async def test_not_exists_context(self):
        ctx = ScenarioPermissionsContext(
            exists=False, department_ids=[], active_simulation_count=0,
        )
        assert ctx.exists is False

    async def test_frozen_dataclass(self):
        ctx = ScenarioPermissionsContext(
            exists=True, department_ids=[], active_simulation_count=0,
        )
        with pytest.raises(AttributeError):
            ctx.exists = False
