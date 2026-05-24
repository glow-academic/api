"""Tests for setting permissions context — monkeypatch DB tool calls."""

from uuid import uuid4

import pytest

from app.infra.setting.permissions_context import (
    SettingPermissionsContext,
    resolve_setting_permissions_context,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestPermissionsContextNotFound:
    async def test_returns_not_exists_when_artifact_missing(self, monkeypatch):
        async def fake_get(conn, ids, **kw):
            return []

        monkeypatch.setattr(
            "app.infra.setting.permissions_context.get_setting_artifacts",
            fake_get,
        )

        result = await resolve_setting_permissions_context(object(), uuid4())
        assert result.exists is False
        assert result.department_ids == []


class TestPermissionsContextDataclass:
    async def test_fields_present(self):
        ctx = SettingPermissionsContext(
            exists=True, department_ids=[uuid4()],
        )
        assert ctx.exists is True
        assert len(ctx.department_ids) == 1

    async def test_not_exists_context(self):
        ctx = SettingPermissionsContext(exists=False, department_ids=[])
        assert ctx.exists is False

    async def test_frozen_dataclass(self):
        ctx = SettingPermissionsContext(exists=True, department_ids=[])
        with pytest.raises(AttributeError):
            ctx.exists = False
