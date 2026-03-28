"""Tests for parameter permissions context — monkeypatch DB tool calls."""

from uuid import uuid4

import pytest

from app.infra.parameter.permissions_context import (
    ParameterPermissionsContext,
    resolve_parameter_permissions_context,
)

pytestmark = pytest.mark.asyncio


class TestPermissionsContextNotFound:
    async def test_returns_not_exists_when_artifact_missing(self, monkeypatch):
        async def fake_get(conn, ids, **kw):
            return []

        monkeypatch.setattr(
            "app.infra.parameter.permissions_context.get_parameter_artifacts",
            fake_get,
        )

        result = await resolve_parameter_permissions_context(object(), uuid4())
        assert result.exists is False
        assert result.department_ids == []
        assert result.active_scenario_count == 0


class TestPermissionsContextDataclass:
    async def test_fields_present(self):
        ctx = ParameterPermissionsContext(
            exists=True, department_ids=[uuid4()], active_scenario_count=0,
        )
        assert ctx.exists is True
        assert len(ctx.department_ids) == 1
        assert ctx.active_scenario_count == 0

    async def test_not_exists_context(self):
        ctx = ParameterPermissionsContext(
            exists=False, department_ids=[], active_scenario_count=0,
        )
        assert ctx.exists is False

    async def test_frozen_dataclass(self):
        ctx = ParameterPermissionsContext(
            exists=True, department_ids=[], active_scenario_count=0,
        )
        with pytest.raises(AttributeError):
            ctx.exists = False
