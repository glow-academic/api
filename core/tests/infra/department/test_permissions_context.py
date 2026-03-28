"""Tests for department permissions context — monkeypatch DB tool calls."""

from uuid import uuid4

import pytest

from app.infra.department.permissions_context import (
    DepartmentPermissionsContext,
    resolve_department_permissions_context,
)

pytestmark = pytest.mark.asyncio


class TestPermissionsContextNotFound:
    async def test_returns_not_exists_when_artifact_missing(self, monkeypatch):
        async def fake_get(conn, ids, **kw):
            return []

        monkeypatch.setattr(
            "app.infra.department.permissions_context.get_department_artifacts",
            fake_get,
        )

        result = await resolve_department_permissions_context(object(), uuid4())
        assert result.exists is False
        assert result.usage_count == 0


class TestPermissionsContextDataclass:
    async def test_fields_present(self):
        ctx = DepartmentPermissionsContext(exists=True, usage_count=5)
        assert ctx.exists is True
        assert ctx.usage_count == 5

    async def test_not_exists_context(self):
        ctx = DepartmentPermissionsContext(exists=False, usage_count=0)
        assert ctx.exists is False

    async def test_frozen_dataclass(self):
        ctx = DepartmentPermissionsContext(exists=True, usage_count=0)
        with pytest.raises(AttributeError):
            ctx.exists = False
