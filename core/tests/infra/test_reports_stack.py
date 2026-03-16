"""Integration tests for the reports infra wrapper family."""

from __future__ import annotations

import pytest

from app.infra.reports.context import resolve_reports_context
from app.infra.reports.docs import docs_reports_impl
from app.infra.reports.export import export_reports_impl
from app.infra.reports.refresh import refresh_reports_impl

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


class TestReportsDocsClient:
    async def test_returns_composed_docs(
        self, pool, redis_client, profile_identity_factory
    ):
        profile = await profile_identity_factory()

        result = await docs_reports_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
        )

        assert result.name == "reports"
        assert result.type == "analytics"
        assert result.page_metadata.list.title == "Reports"
        op_names = {operation.name for operation in result.api_operations}
        assert {"get_reports", "reports_refresh", "export_reports"} <= op_names


class TestExportReportsClient:
    async def test_returns_export_response(
        self, pool, redis_client, profile_identity_factory
    ):
        profile = await profile_identity_factory()

        result = await export_reports_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
        )

        if result.row_count == 0:
            assert result.content == ""
            assert result.file_name == ""
            return

        assert result.file_name.endswith(".zip")
        assert result.mime_type == "application/zip"
        assert result.content != ""
        assert result.row_count > 0


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
