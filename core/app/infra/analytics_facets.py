"""Composable analytics facets resolver.

Any artifact endpoint can call resolve_analytics_facets() with a declarative
config to get filter options (departments, cohorts, date ranges, roles,
attempts) scoped to the requesting user's profile.

Each artifact defines a module-level AnalyticsFacetsConfig constant.
The resolver hydrates it into an AnalyticsFacets Pydantic model that
can be embedded directly in the artifact's response — no separate
/auth/analytics call needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.identity.analytics import (
    AnalyticsFiltersResult,
    resolve_benchmark_filters,
    resolve_health_filters,
    resolve_pricing_filters,
    resolve_profile_facts_filters,
)
from app.infra.identity.simulatable import SIMULATABLE_ROLES
from app.infra.profile_identity_context import ProfileIdentityContext
from app.infra.auth.types import (
    AnalyticsFacets,
    AnalyticsFilterField,
    AnalyticsFilterFields,
    AnalyticsFilterOption,
)
from app.tools.artifacts.cohort.get import get_cohorts as get_cohort_artifacts
from app.tools.artifacts.cohort.search import search_cohorts

# ---------------------------------------------------------------------------
# Convenience constants (re-export for artifact configs)
# ---------------------------------------------------------------------------

HIDDEN = AnalyticsFilterField(visible=False)
VISIBLE = AnalyticsFilterField(visible=True)


# ---------------------------------------------------------------------------
# Declarative config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AnalyticsFacetsConfig:
    """Declarative config for which analytics facets an artifact needs.

    Each artifact defines one of these as a module-level constant, e.g.::

        HOME_FACETS = AnalyticsFacetsConfig(
            fields=AnalyticsFilterFields(
                date_range=VISIBLE, departments=VISIBLE, cohorts=VISIBLE,
                roles=HIDDEN, attempts=HIDDEN,
            ),
            mv_source="profile_facts",
        )
    """

    fields: AnalyticsFilterFields
    mv_source: str  # "profile_facts" | "pricing" | "benchmark" | "health"
    attempt_options: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


async def resolve_analytics_facets(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    config: AnalyticsFacetsConfig,
    profile: ProfileIdentityContext,
    bypass_cache: bool = False,
) -> AnalyticsFacets:
    """Resolve analytics filter facets from a declarative config + profile.

    Composable — call from any artifact's internal function alongside
    existing data fetches (e.g. in an asyncio.gather).  Returns an
    AnalyticsFacets model ready to embed in the artifact's response.
    """
    dept_ids = list(profile.department_ids or [])
    fields = config.fields

    # Resolve cohort resource IDs (needed for profile_facts cohort options)
    cohort_ids: list[UUID] = []
    if profile.profiles_id and fields.cohorts.visible:
        async with pool.acquire() as c:
            cohort_artifact_ids, _ = await search_cohorts(
                c,
                profile_ids=[profile.profiles_id],
                active_only=True,
                limit_count=1000,
            )
        if cohort_artifact_ids:
            async with pool.acquire() as c:
                cohort_arts = await get_cohort_artifacts(
                    c, cohort_artifact_ids, cohorts=True
                )
                for ca in cohort_arts:
                    cohort_ids.extend(ca.cohort_ids or [])

    # Dispatch to the appropriate MV resolver
    result: AnalyticsFiltersResult
    if config.mv_source == "profile_facts":
        result = await resolve_profile_facts_filters(
            pool,
            redis,
            department_ids=dept_ids,
            cohort_ids=cohort_ids,
            need_departments=fields.departments.visible,
            need_cohorts=fields.cohorts.visible,
            need_date_range=fields.date_range.visible,
            bypass_cache=bypass_cache,
        )
    elif config.mv_source == "pricing":
        result = await resolve_pricing_filters(
            pool,
            redis,
            department_ids=dept_ids,
            need_departments=fields.departments.visible,
            need_date_range=fields.date_range.visible,
            bypass_cache=bypass_cache,
        )
    elif config.mv_source == "benchmark":
        result = await resolve_benchmark_filters(
            pool,
            redis,
            department_ids=dept_ids,
            need_departments=fields.departments.visible,
            need_date_range=fields.date_range.visible,
            bypass_cache=bypass_cache,
        )
    elif config.mv_source == "health":
        result = await resolve_health_filters(
            pool,
            need_date_range=fields.date_range.visible,
        )
    else:
        result = AnalyticsFiltersResult()

    # Map infra FilterOption → route AnalyticsFilterOption
    dept_opts = [
        AnalyticsFilterOption(value=o.value, label=o.label)
        for o in result.department_options
    ]
    cohort_opts = [
        AnalyticsFilterOption(value=o.value, label=o.label)
        for o in result.cohort_options
    ]

    # Scoped roles based on user's role
    scoped_roles = list(SIMULATABLE_ROLES.get(profile.role, set()))
    role_options = scoped_roles if fields.roles.visible else []

    return AnalyticsFacets(
        fields=fields,
        department_options=dept_opts,
        cohort_options=cohort_opts,
        role_options=role_options,
        attempt_options=config.attempt_options,
        date_range_earliest=result.date_range_earliest,
        date_range_latest=result.date_range_latest,
    )
