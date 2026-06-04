"""Integration tests for ``refresh_reports_impl``."""

from __future__ import annotations

import pytest

from app.infra.reports.refresh import refresh_reports_impl

pytestmark = pytest.mark.asyncio


class TestRefreshReportsClient:
    async def test_refresh_invalidates_tags(
        self, pool, redis_client, profile_identity_factory
    ):
        profile = await profile_identity_factory()

        result = await refresh_reports_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
        )

        assert result.success is True
        assert result.refreshed_views == []
        assert result.invalidated_tags == ["reports", "artifacts"]
