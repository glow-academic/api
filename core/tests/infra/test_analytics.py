"""Tests for infra.auth.analytics using real black-box setup."""

from datetime import UTC, datetime

import pytest

from app.infra.identity.analytics import (
    AnalyticsFiltersResult,
    resolve_benchmark_filters,
    resolve_health_filters,
    resolve_pricing_filters,
    resolve_profile_facts_filters,
)
from app.tools.artifacts.profile.create import (
    create_profile as create_profile_artifact,
)
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.health.create import create_health
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.test.create import create_test
from app.tools.entries.test.refresh import refresh_test
from app.tools.resources.cohorts.create import create_cohort
from app.tools.resources.departments.create import create_department
from app.tools.resources.profiles.create import create_profile

pytestmark = pytest.mark.asyncio


async def _profile_session_run_call(conn, redis_client):
    profile = await create_profile(conn, redis_client)
    session = await create_session(conn, profile_id=profile.id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(
        conn, group_id=group.id, session_id=session.id, profiles_id=profile.id
    )
    call = await create_call(conn, run_id=run.id, session_id=session.id)
    return profile, session, group, run, call


class TestProfileFactsFilters:
    async def test_returns_department_and_cohort_options(self, pool, redis_client):
        async with pool.acquire() as conn:
            department = await create_department(
                conn, name="Science", redis=redis_client
            )
            cohort = await create_cohort(conn, name="Fall 2025", redis=redis_client)

        result = await resolve_profile_facts_filters(
            pool,
            redis_client,
            department_ids=[department.id],
            cohort_ids=[cohort.id],
            need_date_range=False,
        )

        assert result.department_options[0].value == str(department.id)
        assert result.department_options[0].label == "Science"
        assert result.cohort_options[0].value == str(cohort.id)
        assert result.cohort_options[0].label == "Fall 2025"
        assert result.date_range_earliest is None
        assert result.date_range_latest is None

    async def test_no_department_ids_skips_date_range(self, pool, redis_client):
        result = await resolve_profile_facts_filters(
            pool,
            redis_client,
            department_ids=[],
            cohort_ids=[],
        )

        assert result.date_range_earliest is None
        assert result.date_range_latest is None

    async def test_need_flags_false_returns_empty_filters(self, pool, redis_client):
        async with pool.acquire() as conn:
            department = await create_department(conn, name="Math", redis=redis_client)
            cohort = await create_cohort(conn, name="Spring 2026", redis=redis_client)

        result = await resolve_profile_facts_filters(
            pool,
            redis_client,
            department_ids=[department.id],
            cohort_ids=[cohort.id],
            need_departments=False,
            need_cohorts=False,
            need_date_range=False,
        )

        assert result == AnalyticsFiltersResult()


class TestPricingFilters:
    async def test_returns_departments_and_date_range(self, pool, redis_client):
        async with pool.acquire() as conn:
            department = await create_department(
                conn, name="Engineering", redis=redis_client
            )
            profile, session, group, early_run, _ = await _profile_session_run_call(
                conn, redis_client
            )
            await create_profile_artifact(
                conn,
                department_ids=[department.id],
                profile_ids=[profile.id],
            )
            later_group = await create_group(conn, session_id=session.id)
            late_run = await create_run(
                conn,
                group_id=later_group.id,
                session_id=session.id,
                profiles_id=profile.id,
            )
            await conn.execute(
                "UPDATE runs_entry SET created_at = $2 WHERE id = $1",
                early_run.id,
                datetime(2025, 3, 1, tzinfo=UTC),
            )
            await conn.execute(
                "UPDATE runs_entry SET created_at = $2 WHERE id = $1",
                late_run.id,
                datetime(2025, 9, 15, tzinfo=UTC),
            )
            await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY runs_mv")

        result = await resolve_pricing_filters(
            pool,
            redis_client,
            department_ids=[department.id],
        )

        assert result.department_options[0].label == "Engineering"
        assert result.date_range_earliest == "2025-03-01"
        assert result.date_range_latest == "2025-09-15"

    async def test_need_date_range_false_skips_run_queries(self, pool, redis_client):
        result = await resolve_pricing_filters(
            pool,
            redis_client,
            department_ids=[],
            need_date_range=False,
        )

        assert result.department_options == []
        assert result.date_range_earliest is None
        assert result.date_range_latest is None


class TestBenchmarkFilters:
    async def test_returns_departments_and_date_range(self, pool, redis_client):
        async with pool.acquire() as conn:
            department = await create_department(conn, name="Math", redis=redis_client)
            (
                profile,
                _session,
                _group,
                _run,
                early_call,
            ) = await _profile_session_run_call(conn, redis_client)
            await create_profile_artifact(
                conn,
                department_ids=[department.id],
                profile_ids=[profile.id],
            )
            early_test = await create_test(
                conn, call_id=early_call.id, profiles_id=profile.id
            )
            later_group = await create_group(conn, session_id=_session.id)
            later_run = await create_run(
                conn,
                group_id=later_group.id,
                session_id=_session.id,
                profiles_id=profile.id,
            )
            late_call = await create_call(
                conn, run_id=later_run.id, session_id=_session.id
            )
            late_test = await create_test(
                conn, call_id=late_call.id, profiles_id=profile.id
            )
            await conn.execute(
                "UPDATE test_entry SET created_at = $2 WHERE id = $1",
                early_test.id,
                datetime(2025, 2, 1, tzinfo=UTC),
            )
            await conn.execute(
                "UPDATE test_entry SET created_at = $2 WHERE id = $1",
                late_test.id,
                datetime(2025, 11, 1, tzinfo=UTC),
            )
            await refresh_test(conn)

        result = await resolve_benchmark_filters(
            pool,
            redis_client,
            department_ids=[department.id],
        )

        assert result.department_options[0].label == "Math"
        assert result.date_range_earliest == "2025-02-01T00:00:00+00:00"
        assert result.date_range_latest == "2025-11-01T00:00:00+00:00"

    async def test_need_date_range_false_skips_test_queries(self, pool, redis_client):
        result = await resolve_benchmark_filters(
            pool,
            redis_client,
            department_ids=[],
            need_date_range=False,
        )

        assert result.department_options == []
        assert result.date_range_earliest is None
        assert result.date_range_latest is None


class TestHealthFilters:
    async def test_returns_date_range(self, pool):
        async with pool.acquire() as conn:
            await create_health(
                conn,
                service="redis",
                ok=True,
                latency_ms=20.0,
                ts=datetime(2034, 1, 1, tzinfo=UTC),
            )
            await create_health(
                conn,
                service="redis",
                ok=False,
                latency_ms=35.0,
                ts=datetime(2035, 12, 31, tzinfo=UTC),
                error="timeout",
            )
            await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY health_mv")

        result = await resolve_health_filters(pool)

        assert result.date_range_latest == "2035-12-31T00:00:00+00:00"
        assert result.department_options == []
        assert result.cohort_options == []

    async def test_need_date_range_false_skips(self, pool):
        result = await resolve_health_filters(pool, need_date_range=False)
        assert result == AnalyticsFiltersResult()
