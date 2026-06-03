"""Integration tests for ``resolve_reports_context``."""

from __future__ import annotations

import pytest

from app.infra.reports.context import resolve_reports_context

pytestmark = pytest.mark.asyncio


class TestResolveReportsContext:
    async def test_returns_empty_chat_items_and_thresholds(
        self, pool, redis_client, profile_identity_factory
    ):
        profile = await profile_identity_factory()

        result = await resolve_reports_context(
            pool,
            redis_client,
            actor_profile_id=profile.artifact_id,
            target_profile_id=profile.profile_resource_id,
        )

        assert result.artifact_id is None
        assert result.entries["chat_items"] == []
        assert result.entries["thresholds"][0]["success"] == 85
        assert result.resources["profiles"].selected == []
        assert result.resources["simulations"].selected == []
