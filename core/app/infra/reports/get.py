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
from app.infra.api_types import FilterOption
from app.infra.auth.types import AnalyticsFilterFields
from app.infra.common_context import resolve_common_context
from app.infra.dashboard.visibility import resolve_visible_profile_ids
from app.infra.reports.context import resolve_reports_context
from app.infra.reports.permissions import build_reports_sections_v2
from app.infra.reports.types import (
    ReportsCohortResource,
    ReportsProfileResource,
    ReportsRequest,
    ReportsResources,
    ReportsResponse,
    ReportsRoleResource,
    ReportsScenarioResource,
    ReportsSections,
    ReportsSimulationResource,
    ReportsViews,
)

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
    request: ReportsRequest | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> ReportsResponse:
    """Resolve the canonical reports response for any surface.

    See ``get_pricing_impl`` — same optional-request convention so the
    tool-dispatch path can call without pre-building the Pydantic wrapper.
    """
    if request is None:
        request = ReportsRequest(**{
            k: v for k, v in _kwargs.items() if k in ReportsRequest.model_fields
        })
    common = await resolve_common_context(
        pool, redis, profile_id=profile_id, bypass_cache=bypass_cache
    )
    if not common:
        raise HTTPException(status_code=401, detail="Profile not found")

    # Authorization: reports has no scoping of its own, so apply the canonical
    # visibility policy here. ``resolve_visible_profile_ids`` returns exactly
    # the profiles this actor may see (self + same-department lower-privilege
    # profiles, or the entire org for role_level 0). A caller-supplied
    # ``target_profile_id`` is allowed only if it is in that set; otherwise the
    # caller could read any profile's analytics by supplying its id (IDOR,
    # #145). ``department_ids`` are likewise constrained to the actor's own
    # departments (superadmin/role_level 0 is unconstrained).
    visible_profile_ids = await resolve_visible_profile_ids(pool, common.profile)
    if (
        request.target_profile_id is not None
        and request.target_profile_id not in visible_profile_ids
    ):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to view analytics for this profile.",
        )

    if request.department_ids and common.profile.role_level != 0:
        allowed_departments = set(common.profile.department_ids or [])
        scoped_department_ids = [
            dept_id
            for dept_id in request.department_ids
            if dept_id in allowed_departments
        ]
        if not scoped_department_ids:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to view analytics for these departments.",
            )
    else:
        scoped_department_ids = request.department_ids

    # When no explicit target/department scope is supplied, restrict the search
    # to the actor's visible set so reports defaults to a scoped org view rather
    # than every profile in the system.
    effective_profile_ids: list | None = None
    if request.target_profile_id is None and not scoped_department_ids:
        effective_profile_ids = visible_profile_ids

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
            visible_profile_ids=effective_profile_ids,
            actor_profile_id=request.actor_profile_id,
            cohort_ids=request.cohort_ids,
            department_ids=scoped_department_ids,
            simulation_ids=request.simulation_ids,
            role_ids=request.role_ids,
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
    roles = ctx.resources.get("roles")
    sim_selected = simulations.selected if simulations else []
    prof_selected = profiles.selected if profiles else []
    scen_selected = scenarios.selected if scenarios else []
    cohort_selected = cohorts.selected if cohorts else []
    role_selected = roles.selected if roles else []
    role_map = {item.id: item for item in role_selected if item.id}

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
                role_id=str(item.role_id) if item.role_id else None,
                role=role_map[item.role_id].name
                if item.role_id and item.role_id in role_map
                else None,
                emails=item.emails or [],
                primary_email=item.primary_email,
            )
            for item in prof_selected
        },
        roles={
            str(item.id): ReportsRoleResource(
                role_id=str(item.id),
                name=item.name,
                description=item.description,
                icon_id=str(item.icon_id) if item.icon_id else None,
                color_id=str(item.color_id) if item.color_id else None,
                level=item.level,
            )
            for item in role_selected
            if item.id
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
