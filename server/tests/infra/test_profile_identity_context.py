"""Integration tests for infra.profile_identity_context — real DB, no mocks."""

import pytest
from tests.helpers import nonexistent_id, unique_tag

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.profile.create import (
    create_profile as create_profile_artifact,
)
from app.tools.artifacts.profile.update import (
    update_profile as update_profile_artifact,
)
from app.tools.resources.names.create import create_name

pytestmark = pytest.mark.asyncio


class TestResolveProfileIdentityContext:
    async def test_nonexistent_profile_returns_none(self, pool, redis_client):
        result = await resolve_profile_identity_context(
            pool,
            nonexistent_id(),
            redis_client,
        )

        assert result is None

    async def test_artifact_without_profiles_junction_returns_none(
        self, pool, redis_client
    ):
        async with pool.acquire() as conn:
            name_res = await create_name(
                conn, f"no-profile-{unique_tag()}", redis_client
            )
            artifact_res = await create_profile_artifact(conn, name_id=name_res.id)

        result = await resolve_profile_identity_context(
            pool,
            artifact_res.id,
            redis_client,
        )

        assert result is None

    async def test_full_hydration_from_real_data(
        self, pool, redis_client, profile_identity_factory
    ):
        profile = await profile_identity_factory(
            name="Jane Doe",
            departments=["Engineering", "Research"],
            emails=["jane@example.com", "jane@org.com"],
        )

        result = await resolve_profile_identity_context(
            pool,
            profile.artifact_id,
            redis_client,
        )

        assert result is not None
        assert result.profiles_id == profile.profile_resource_id
        assert result.name == profile.name
        assert result.role == profile.role
        assert result.role_name == profile.role_name
        assert result.role_description == profile.role_description
        assert result.role_artifacts == profile.role_artifacts
        assert result.primary_email is None
        assert result.emails == profile.emails
        assert result.primary_department_id is None
        assert len(result.department_ids) == len(profile.departments)
        assert result.settings_id is None
        assert result.requests_per_day is None
        assert result.is_active is True
        assert result.session_id is None
        assert result.group_id is None

    async def test_no_role_returns_empty_role_fields(
        self, pool, redis_client, profile_identity_factory
    ):
        profile = await profile_identity_factory(
            role=None,
            departments=[],
            emails=[],
        )

        result = await resolve_profile_identity_context(
            pool,
            profile.artifact_id,
            redis_client,
        )

        assert result is not None
        assert result.role == ""
        assert result.role_name == ""
        assert result.role_description == ""
        assert result.role_artifacts == []

    async def test_inactive_artifact_returns_inactive_context(
        self, pool, redis_client, profile_identity_factory
    ):
        profile = await profile_identity_factory(
            artifact_active=True,
        )

        async with pool.acquire() as conn:
            await update_profile_artifact(conn, profile.artifact_id, active=False)

        result = await resolve_profile_identity_context(
            pool,
            profile.artifact_id,
            redis_client,
        )

        assert result is not None
        assert result.is_active is False

    async def test_primary_department_setting_is_resolved(
        self, pool, redis_client, setting_graph_factory
    ):
        fixture = await setting_graph_factory()

        result = await resolve_profile_identity_context(
            pool,
            fixture.profile_artifact_id,
            redis_client,
        )

        assert result is not None
        assert result.profiles_id == fixture.profile_resource_id
        assert result.primary_department_id == fixture.department_id
        assert result.settings_id == fixture.setting_id
