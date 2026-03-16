"""Resolve analytics filters — composes canonical black boxes.

Given a page config + profile access data:
  1. get_departments / get_cohorts → filter option labels
  2. search_attempt_chats / search_runs / search_tests / search_health → date ranges

No inline SQL.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.profile.get import (
    get_profiles as get_profile_artifacts,
)
from app.tools.artifacts.profile.search import search_profiles
from app.tools.entries.attempt_chat.search import search_attempt_chats
from app.tools.entries.health.search import search_health
from app.tools.entries.runs.search import search_runs
from app.tools.entries.test.search import search_tests
from app.tools.resources.cohorts.get import get_cohorts
from app.tools.resources.departments.get import get_departments


@dataclass(frozen=True)
class FilterOption:
    """A single filter option (value + label)."""

    value: str
    label: str


@dataclass(frozen=True)
class AnalyticsFiltersResult:
    """Result of resolving analytics filter options."""

    department_options: list[FilterOption] = field(default_factory=list)
    cohort_options: list[FilterOption] = field(default_factory=list)
    date_range_earliest: str | None = None
    date_range_latest: str | None = None


async def resolve_profile_facts_filters(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    department_ids: list[UUID],
    cohort_ids: list[UUID],
    need_departments: bool = True,
    need_cohorts: bool = True,
    need_date_range: bool = True,
    bypass_cache: bool = False,
) -> AnalyticsFiltersResult:
    """Resolve filter options from attempt_chat_mv via black boxes."""

    async def _fetch_departments() -> list[FilterOption]:
        if not need_departments or not department_ids:
            return []
        async with pool.acquire() as c:
            items = await get_departments(
                c, department_ids, redis, bypass_cache=bypass_cache
            )
            return [
                FilterOption(value=str(d.id), label=d.name or "")
                for d in sorted(items, key=lambda d: d.name or "")
            ]

    async def _fetch_cohorts() -> list[FilterOption]:
        if not need_cohorts or not cohort_ids:
            return []
        async with pool.acquire() as c:
            items = await get_cohorts(c, cohort_ids, redis, bypass_cache=bypass_cache)
            return [
                FilterOption(value=str(c.id), label=c.name or "")
                for c in sorted(items, key=lambda c: c.name or "")
            ]

    async def _fetch_date_range() -> tuple[str | None, str | None]:
        if not need_date_range or not department_ids:
            return None, None
        async with pool.acquire() as c_earliest, pool.acquire() as c_latest:
            (earliest_items, _), (latest_items, _) = await asyncio.gather(
                search_attempt_chats(
                    c_earliest,
                    department_ids=department_ids,
                    sort_order="asc",
                    limit=1,
                ),
                search_attempt_chats(
                    c_latest,
                    department_ids=department_ids,
                    sort_order="desc",
                    limit=1,
                ),
            )
        earliest = (
            earliest_items[0].attempt_date.isoformat()
            if earliest_items and earliest_items[0].attempt_date
            else None
        )
        latest = (
            latest_items[0].attempt_date.isoformat()
            if latest_items and latest_items[0].attempt_date
            else None
        )
        return earliest, latest

    dept_opts, cohort_opts, (earliest, latest) = await asyncio.gather(
        _fetch_departments(),
        _fetch_cohorts(),
        _fetch_date_range(),
    )

    return AnalyticsFiltersResult(
        department_options=dept_opts,
        cohort_options=cohort_opts,
        date_range_earliest=earliest,
        date_range_latest=latest,
    )


async def resolve_pricing_filters(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    department_ids: list[UUID],
    need_departments: bool = True,
    need_date_range: bool = True,
    bypass_cache: bool = False,
) -> AnalyticsFiltersResult:
    """Resolve filter options for pricing pages via black boxes."""

    async def _fetch_departments() -> list[FilterOption]:
        if not need_departments or not department_ids:
            return []
        async with pool.acquire() as c:
            items = await get_departments(
                c, department_ids, redis, bypass_cache=bypass_cache
            )
            return [
                FilterOption(value=str(d.id), label=d.name or "")
                for d in sorted(items, key=lambda d: d.name or "")
            ]

    async def _fetch_date_range() -> tuple[str | None, str | None]:
        if not need_date_range:
            return None, None
        profile_resource_ids: list[UUID] | None = None
        if department_ids:
            async with pool.acquire() as c_profiles:
                profile_artifact_ids, _ = await search_profiles(
                    c_profiles,
                    department_ids=department_ids,
                    active_only=False,
                    limit_count=100000,
                    offset_count=0,
                )
                if profile_artifact_ids:
                    artifacts = await get_profile_artifacts(
                        c_profiles,
                        profile_artifact_ids,
                        active=None,
                        profiles=True,
                    )
                    profile_resource_ids = [
                        resource_id
                        for artifact in artifacts
                        for resource_id in (artifact.profile_ids or [])
                    ]
                else:
                    profile_resource_ids = []

        async with pool.acquire() as c_earliest, pool.acquire() as c_latest:
            (earliest_items, _), (latest_items, _) = await asyncio.gather(
                search_runs(
                    conn=c_earliest,
                    profiles_ids=profile_resource_ids,
                    sort_order="asc",
                    limit=1,
                ),
                search_runs(
                    conn=c_latest,
                    profiles_ids=profile_resource_ids,
                    sort_order="desc",
                    limit=1,
                ),
            )
        earliest = None
        latest = None
        if earliest_items and earliest_items[0].run_created_at:
            earliest = earliest_items[0].run_created_at.date().isoformat()
        if latest_items and latest_items[0].run_created_at:
            latest = latest_items[0].run_created_at.date().isoformat()
        return earliest, latest

    dept_opts, (earliest, latest) = await asyncio.gather(
        _fetch_departments(),
        _fetch_date_range(),
    )

    return AnalyticsFiltersResult(
        department_options=dept_opts,
        date_range_earliest=earliest,
        date_range_latest=latest,
    )


async def resolve_benchmark_filters(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    department_ids: list[UUID],
    need_departments: bool = True,
    need_date_range: bool = True,
    bypass_cache: bool = False,
) -> AnalyticsFiltersResult:
    """Resolve filter options for benchmark pages via black boxes."""

    async def _fetch_departments() -> list[FilterOption]:
        if not need_departments or not department_ids:
            return []
        async with pool.acquire() as c:
            items = await get_departments(
                c, department_ids, redis, bypass_cache=bypass_cache
            )
            return [
                FilterOption(value=str(d.id), label=d.name or "")
                for d in sorted(items, key=lambda d: d.name or "")
            ]

    async def _fetch_date_range() -> tuple[str | None, str | None]:
        if not need_date_range:
            return None, None
        profile_resource_ids: list[UUID] | None = None
        if department_ids:
            async with pool.acquire() as c_profiles:
                profile_artifact_ids, _ = await search_profiles(
                    c_profiles,
                    department_ids=department_ids,
                    active_only=False,
                    limit_count=100000,
                    offset_count=0,
                )
                if profile_artifact_ids:
                    artifacts = await get_profile_artifacts(
                        c_profiles,
                        profile_artifact_ids,
                        active=None,
                        profiles=True,
                    )
                    profile_resource_ids = [
                        resource_id
                        for artifact in artifacts
                        for resource_id in (artifact.profile_ids or [])
                    ]
                else:
                    profile_resource_ids = []

        async with pool.acquire() as c_earliest, pool.acquire() as c_latest:
            # Fetch earliest and latest in parallel
            earliest_items, _ = await search_tests(
                c_earliest,
                profile_ids=profile_resource_ids,
                sort_order="asc",
                limit=1,
            )
            latest_items, _ = await search_tests(
                c_latest,
                profile_ids=profile_resource_ids,
                sort_order="desc",
                limit=1,
            )
        earliest = (
            earliest_items[0].test_created_at.isoformat() if earliest_items else None
        )
        latest = latest_items[0].test_created_at.isoformat() if latest_items else None
        return earliest, latest

    dept_opts, (earliest, latest) = await asyncio.gather(
        _fetch_departments(),
        _fetch_date_range(),
    )

    return AnalyticsFiltersResult(
        department_options=dept_opts,
        date_range_earliest=earliest,
        date_range_latest=latest,
    )


async def resolve_health_filters(
    pool: asyncpg.Pool,
    *,
    need_date_range: bool = True,
) -> AnalyticsFiltersResult:
    """Resolve filter options for health page via black boxes."""
    if not need_date_range:
        return AnalyticsFiltersResult()

    async with pool.acquire() as c_earliest, pool.acquire() as c_latest:
        earliest_items, latest_items = await asyncio.gather(
            search_health(c_earliest, sort_order="asc", limit=1),
            search_health(c_latest, sort_order="desc", limit=1),
        )

    earliest = earliest_items[0].date_hour.isoformat() if earliest_items else None
    latest = latest_items[0].date_hour.isoformat() if latest_items else None

    return AnalyticsFiltersResult(
        date_range_earliest=earliest,
        date_range_latest=latest,
    )
