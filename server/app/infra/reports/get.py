"""Canonical shared reports GET operation."""

from __future__ import annotations

import asyncio
from datetime import datetime

from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.analytics_facets import (
    VISIBLE,
    AnalyticsFacetsConfig,
    resolve_analytics_facets,
)
from app.infra.common_context import resolve_common_context
from app.infra.reports.context import resolve_reports_context
from app.infra.reports.permissions import build_reports_sections_v2
from app.infra.auth.types import AnalyticsFilterFields
from app.infra.reports.types import (
    ReportsCohortResource,
    ReportsProfileResource,
    ReportsRequest,
    ReportsResources,
    ReportsResponse,
    ReportsScenarioResource,
    ReportsSections,
    ReportsSimulationResource,
    ReportsViews,
)
from app.infra.v5_types import FilterOption

REPORTS_FACETS_CONFIG = AnalyticsFacetsConfig(
    fields=AnalyticsFilterFields(
        date_range=VISIBLE,
        departments=VISIBLE,
        cohorts=VISIBLE,
        roles=VISIBLE,
        attempts=VISIBLE,
    ),
    mv_source="profile_facts",
    attempt_options=["general", "practice", "archived"],
)


async def get_reports_impl(
    pool,
    redis: Redis,
    *,
    profile_id,
    request: ReportsRequest,
    bypass_cache: bool = False,
) -> ReportsResponse:
    """Resolve the canonical reports response for any surface."""
    common = await resolve_common_context(
        pool, redis, profile_id=profile_id, bypass_cache=bypass_cache
    )
    if not common:
        raise HTTPException(status_code=401, detail="Profile not found")

    parsed_start_date = (
        datetime.fromisoformat(request.start_date.replace("Z", "+00:00"))
        if request.start_date
        else None
    )
    parsed_end_date = (
        datetime.fromisoformat(request.end_date.replace("Z", "+00:00"))
        if request.end_date
        else None
    )
    parsed_start_day = parsed_start_date.date() if parsed_start_date else None
    parsed_end_day = parsed_end_date.date() if parsed_end_date else None

    is_archived = bool(
        request.simulation_filters and "archived" in request.simulation_filters
    )
    if request.simulation_filters and "general" in request.simulation_filters:
        attempt_type = "general"
    elif request.simulation_filters and "practice" in request.simulation_filters:
        attempt_type = "practice"
    else:
        attempt_type = None

    ctx, analytics_facets = await asyncio.gather(
        resolve_reports_context(
            pool,
            redis,
            target_profile_id=request.target_profile_id,
            actor_profile_id=request.actor_profile_id,
            cohort_ids=request.cohort_ids,
            department_ids=request.department_ids,
            simulation_ids=request.simulation_ids,
            attempt_type=attempt_type,
            is_archived=is_archived,
            date_from=parsed_start_day,
            date_to=parsed_end_day,
            bypass_cache=bypass_cache,
        ),
        resolve_analytics_facets(
            pool,
            redis,
            config=REPORTS_FACETS_CONFIG,
            profile=common.profile,
            bypass_cache=bypass_cache,
        ),
    )

    chat_items = ctx.entries.get("chat_items", [])
    thresholds = ctx.entries.get("thresholds", [{}])[0]
    total_count = len(chat_items)

    sections = build_reports_sections_v2(
        profile_facts_items=chat_items,
        total_count=total_count,
        thresholds=thresholds,
    )

    views = ReportsViews(
        attempt_facts=[],
        chat_facts=[],
        daily_metrics=[],
        profile_metrics=[],
    )

    simulations = ctx.resources.get("simulations")
    profiles = ctx.resources.get("profiles")
    scenarios = ctx.resources.get("scenarios")
    cohorts = ctx.resources.get("cohorts")
    sim_selected = simulations.selected if simulations else []
    prof_selected = profiles.selected if profiles else []
    scen_selected = scenarios.selected if scenarios else []
    cohort_selected = cohorts.selected if cohorts else []

    resources = ReportsResources(
        simulations={
            str(item.id): ReportsSimulationResource(
                simulation_id=str(item.id),
                name=item.name,
                description=item.description,
            )
            for item in sim_selected
        },
        profiles={
            str(item.id): ReportsProfileResource(
                profile_id=str(item.id),
                name=item.name,
                role=None,
                emails=item.emails or [],
                primary_email=item.primary_email,
            )
            for item in prof_selected
        },
        scenarios={
            str(item.id): ReportsScenarioResource(
                scenario_id=str(item.id),
                name=item.name,
                description=item.description,
            )
            for item in scen_selected
        },
        cohorts={
            str(item.id): ReportsCohortResource(
                cohort_id=str(item.id),
                name=item.name,
            )
            for item in cohort_selected
        },
        personas={},
        rubrics={},
    )

    simulation_options = [
        FilterOption(value=item_id, label=resources.simulations[item_id].name)
        for item_id in resources.simulations
        if resources.simulations[item_id].name
    ]
    profile_options = [
        FilterOption(value=item_id, label=resources.profiles[item_id].name)
        for item_id in resources.profiles
        if resources.profiles[item_id].name
    ]
    scenario_options = [
        FilterOption(value=item_id, label=resources.scenarios[item_id].name)
        for item_id in resources.scenarios
        if resources.scenarios[item_id].name
    ]

    return ReportsResponse(
        sections=ReportsSections.model_validate(sections.model_dump()),
        views=views,
        resources=resources,
        total_count=total_count,
        simulation_options=simulation_options,
        profile_options=profile_options,
        scenario_options=scenario_options,
        analytics=analytics_facets,
    )
