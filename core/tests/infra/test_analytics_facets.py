"""Tests for analytics facets composition."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.infra.analytics_facets import (
    HIDDEN,
    VISIBLE,
    AnalyticsFacetsConfig,
    resolve_analytics_facets,
)
from app.infra.profile_identity_context import ProfileIdentityContext
from app.infra.auth.types import AnalyticsFilterFields
from app.tools.artifacts.cohort.create import (
    create_cohort as create_cohort_artifact,
)
from app.tools.artifacts.profile.create import (
    create_profile as create_profile_artifact,
)
from app.tools.entries.groups.create import create_group
from app.tools.entries.health.create import create_health
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.resources.cohorts.create import create_cohort
from app.tools.resources.departments.create import create_department
from app.tools.resources.profiles.create import create_profile

pytestmark = pytest.mark.asyncio


def _profile_context(
    *, profiles_id, department_ids, role="superadmin"
) -> ProfileIdentityContext:
    return ProfileIdentityContext(
        profiles_id=profiles_id,
        name="Test User",
        role=role,
        role_name=role.title(),
        role_description="role",
        role_artifacts=[],
        primary_email="test@example.com",
        emails=["test@example.com"],
        primary_department_id=department_ids[0] if department_ids else None,
        department_ids=department_ids,
        settings_id=None,
        requests_per_day=100,
        is_active=True,
    )


async def test_profile_facts_facets_resolve_department_cohort_and_roles(
    pool, redis_client
):
    async with pool.acquire() as conn:
        department = await create_department(conn, name="Science", redis=redis_client)
        cohort_resource = await create_cohort(
            conn, name="Fall 2025", redis=redis_client
        )
        profile = await create_profile(conn, redis_client)
        await create_cohort_artifact(
            conn,
            profile_ids=[profile.id],
            cohort_ids=[cohort_resource.id],
        )

    facets = await resolve_analytics_facets(
        pool,
        redis_client,
        config=AnalyticsFacetsConfig(
            fields=AnalyticsFilterFields(
                date_range=VISIBLE,
                departments=VISIBLE,
                cohorts=VISIBLE,
                roles=VISIBLE,
                attempts=VISIBLE,
            ),
            mv_source="profile_facts",
            attempt_options=["first_attempt", "latest_attempt"],
        ),
        profile=_profile_context(
            profiles_id=profile.id,
            department_ids=[department.id],
        ),
    )

    assert facets.department_options[0].label == "Science"
    assert facets.cohort_options[0].label == "Fall 2025"
    assert "admin" in facets.role_options
    assert facets.attempt_options == ["first_attempt", "latest_attempt"]


async def test_pricing_facets_resolve_departments_and_date_range(pool, redis_client):
    async with pool.acquire() as conn:
        department = await create_department(
            conn, name="Engineering", redis=redis_client
        )
        profile = await create_profile(conn, redis_client)
        await create_profile_artifact(
            conn,
            department_ids=[department.id],
            profile_ids=[profile.id],
        )
        session = await create_session(conn, profile_id=profile.id)
        group = await create_group(conn, session_id=session.id)
        run = await create_run(
            conn, group_id=group.id, session_id=session.id, profiles_id=profile.id
        )
        await conn.execute(
            "UPDATE runs_entry SET created_at = $2 WHERE id = $1",
            run.id,
            datetime(2030, 5, 1, tzinfo=UTC),
        )
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY runs_mv")

    facets = await resolve_analytics_facets(
        pool,
        redis_client,
        config=AnalyticsFacetsConfig(
            fields=AnalyticsFilterFields(
                date_range=VISIBLE,
                departments=VISIBLE,
                roles=HIDDEN,
            ),
            mv_source="pricing",
        ),
        profile=_profile_context(
            profiles_id=profile.id,
            department_ids=[department.id],
            role="admin",
        ),
    )

    assert facets.department_options[0].label == "Engineering"
    assert facets.date_range_latest == "2030-05-01"
    assert facets.role_options == []


async def test_health_facets_resolve_date_range_only(pool, redis_client):
    async with pool.acquire() as conn:
        await create_health(
            conn,
            service="redis",
            ok=True,
            latency_ms=12.0,
            ts=datetime(2036, 6, 1, tzinfo=UTC),
        )
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY health_mv")

    facets = await resolve_analytics_facets(
        pool,
        redis_client,
        config=AnalyticsFacetsConfig(
            fields=AnalyticsFilterFields(date_range=VISIBLE),
            mv_source="health",
        ),
        profile=_profile_context(
            profiles_id=uuid4(),
            department_ids=[],
            role="guest",
        ),
    )

    assert facets.department_options == []
    assert facets.cohort_options == []
    assert facets.date_range_latest == "2036-06-01T00:00:00+00:00"
