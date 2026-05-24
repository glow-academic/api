"""Tests for cohort permissions context — monkeypatch DB tool calls."""

from uuid import uuid4

import pytest

from app.infra.cohort.permissions_context import (
    CohortPermissionsContext,
    resolve_cohort_permissions_context,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestPermissionsContextNotFound:
    async def test_returns_not_exists_when_artifact_missing(self, monkeypatch):
        async def fake_get(conn, ids, **kw):
            return []

        monkeypatch.setattr(
            "app.infra.cohort.permissions_context.get_cohort_artifacts",
            fake_get,
        )

        result = await resolve_cohort_permissions_context(object(), uuid4())
        assert result.exists is False
        assert result.department_ids == []


class TestPermissionsContextDataclass:
    async def test_fields_present(self):
        ctx = CohortPermissionsContext(
            exists=True, department_ids=[uuid4()],
        )
        assert ctx.exists is True
        assert len(ctx.department_ids) == 1

    async def test_not_exists_context(self):
        ctx = CohortPermissionsContext(exists=False, department_ids=[])
        assert ctx.exists is False

    async def test_frozen_dataclass(self):
        ctx = CohortPermissionsContext(exists=True, department_ids=[])
        with pytest.raises(AttributeError):
            ctx.exists = False
