"""Integration tests for ``export_reports_impl``."""

from __future__ import annotations

import pytest

from app.infra.reports.export import export_reports_impl

pytestmark = pytest.mark.asyncio


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
