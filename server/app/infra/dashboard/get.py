"""Canonical shared dashboard get operations."""

from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException

from app.infra.analytics_facets import (
    VISIBLE,
    AnalyticsFacetsConfig,
    resolve_analytics_facets,
)
from app.infra.common_context import resolve_common_context
from app.infra.dashboard.builders import (
    build_field_meta,
    build_parameter_meta,
    build_rubric_meta,
    build_scenario_meta,
    build_simulation_meta,
)
from app.infra.dashboard.context import (
    resolve_dashboard_context,
    resolve_dashboard_search_context,
)
from app.infra.dashboard.permissions import (
    compute_footer_metrics_v2,
    compute_header_metrics_v2,
    compute_primary_metrics_v2,
    compute_secondary_metrics_v2,
)
from app.infra.globals import get_redis_client
from app.infra.auth.types import AnalyticsFilterFields
from app.routes.v5.dashboard.search import _build_history_response
from app.infra.dashboard.types import (
    DashboardBundleResponse,
    DashboardRequest,
)
from app.infra.v5_types import FilterOption
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

DASHBOARD_FACETS_CONFIG = AnalyticsFacetsConfig(
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


async def get_dashboard_impl_cached(
    pool,
    request: DashboardRequest,
    *,
    profile_id: UUID,
    bypass_cache: bool = False,
    cache_key_path: str = "/v5/dashboard/get",
) -> tuple[DashboardBundleResponse, bool]:
    tags = ["artifacts", "dashboard", "views", "analytics"]
    cache_key_val = cache_key(cache_key_path, request.model_dump(mode="json"))

    if not bypass_cache:
        cached = await get_cached(cache_key_val, redis=get_redis_client())
        if cached:
            return DashboardBundleResponse.model_validate(cached["data"]), True

    redis = get_redis_client()
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
        resolve_dashboard_context(
            pool,
            redis,
            target_profile_id=request.target_profile_id,
            actor_profile_id=request.actor_profile_id,
            cohort_ids=request.cohort_ids,
            department_ids=request.department_ids,
            simulation_ids=request.simulation_ids,
            attempt_type=attempt_type,
            is_archived=is_archived,
            date_from=parsed_start_date.date() if parsed_start_date else None,
            date_to=parsed_end_date.date() if parsed_end_date else None,
            bypass_cache=bypass_cache,
        ),
        resolve_analytics_facets(
            pool,
            redis,
            config=DASHBOARD_FACETS_CONFIG,
            profile=common.profile,
            bypass_cache=bypass_cache,
        ),
    )

    chat_items = ctx.entries.get("chat_items", [])
    rubric_items = ctx.entries.get("rubric_items", [])
    thresholds_list = ctx.entries.get("thresholds", [])
    scenario_count_rows = ctx.entries.get("scenario_counts", [])
    cohort_name_rows = ctx.entries.get("cohort_names", [])

    simulations = (
        ctx.resources.get("simulations").selected
        if ctx.resources.get("simulations")
        else []
    )
    scenarios_list = (
        ctx.resources.get("scenarios").selected
        if ctx.resources.get("scenarios")
        else []
    )
    personas = (
        ctx.resources.get("personas").selected if ctx.resources.get("personas") else []
    )
    rubrics = (
        ctx.resources.get("rubrics").selected if ctx.resources.get("rubrics") else []
    )
    standard_groups = (
        ctx.resources.get("standard_groups").selected
        if ctx.resources.get("standard_groups")
        else []
    )
    documents = (
        ctx.resources.get("documents").selected
        if ctx.resources.get("documents")
        else []
    )
    parameter_fields = (
        ctx.resources.get("parameter_fields").selected
        if ctx.resources.get("parameter_fields")
        else []
    )
    parameters = (
        ctx.resources.get("parameters").selected
        if ctx.resources.get("parameters")
        else []
    )
    fields_list = (
        ctx.resources.get("fields").selected if ctx.resources.get("fields") else []
    )
    target_profiles = (
        ctx.resources.get("profiles").selected if ctx.resources.get("profiles") else []
    )

    thresholds_dict = (
        thresholds_list[0]
        if thresholds_list
        else {"success": 85, "warning": 80, "danger": 70}
    )

    simulation_scenario_counts = {
        str(r["simulation_id"]): r["scenario_count"] for r in scenario_count_rows
    }
    persona_name_map = {
        str(p.persona_id): p.name for p in personas if p.persona_id and p.name
    }
    cohort_name_map = {
        str(r["id"]): r["name"] for r in cohort_name_rows if r["id"] and r["name"]
    }
    simulation_name_map = {
        str(s.simulation_id): s.name for s in simulations if s.simulation_id and s.name
    }
    scenario_name_map = {
        str(s.scenario_id): s.name for s in scenarios_list if s.scenario_id and s.name
    }
    standard_group_name_map = {
        str(getattr(sg, "standard_group_id", None)): getattr(sg, "name", "")
        for sg in standard_groups
        if getattr(sg, "standard_group_id", None) and getattr(sg, "name", None)
    }
    field_parameter_map: dict[UUID, UUID] = {}
    for pf in parameter_fields:
        if pf.field_id and pf.parameter_id:
            field_parameter_map[pf.field_id] = pf.parameter_id

    header_metrics = compute_header_metrics_v2(
        profile_facts_items=chat_items,
        simulation_scenario_counts=simulation_scenario_counts,
        thresholds=thresholds_dict,
    )
    primary_metrics = compute_primary_metrics_v2(
        rubric_facts=rubric_items,
        standard_group_name_map=standard_group_name_map,
        thresholds=thresholds_dict,
    )
    secondary_metrics = compute_secondary_metrics_v2(
        simulation_facts=chat_items,
        persona_name_map=persona_name_map,
        cohort_name_map=cohort_name_map,
        thresholds=thresholds_dict,
    )
    footer_metrics = compute_footer_metrics_v2(
        scenario_facts_items=chat_items,
        scenarios=scenarios_list,
        personas=personas,
        documents=documents,
        parameter_fields=parameter_fields,
        parameters=parameters,
        fields=fields_list,
        simulation_name_map=simulation_name_map,
        scenario_name_map=scenario_name_map,
        thresholds=thresholds_dict,
    )

    if request.rubric_ids:
        filter_set = {str(rid) for rid in request.rubric_ids}
        primary_metrics.rubric_heatmap.matrices = [
            m
            for m in primary_metrics.rubric_heatmap.matrices
            if m.rubric_id in filter_set
        ]
        primary_metrics.skill_performance.packages = [
            p
            for p in primary_metrics.skill_performance.packages
            if p.rubric_id in filter_set
        ]

    if request.simulation_picker_ids:
        filter_set = {str(sid) for sid in request.simulation_picker_ids}
        secondary_metrics.persona_performance.chart_data = [
            row
            for row in secondary_metrics.persona_performance.chart_data
            if any(sid in filter_set for sid in (row.simulation_ids or []))
        ]
        secondary_metrics.cohort_performance.simulation_facts = [
            f
            for f in secondary_metrics.cohort_performance.simulation_facts
            if f.simulation_id in filter_set
        ]
        secondary_metrics.cohort_performance.daily_facts = [
            f
            for f in secondary_metrics.cohort_performance.daily_facts
            if f.simulation_id in filter_set
        ]
        secondary_metrics.attempt_improvement.facts = [
            f
            for f in secondary_metrics.attempt_improvement.facts
            if f.simulation_id in filter_set
        ]

    if request.parameter_ids:
        filter_set = {str(pid) for pid in request.parameter_ids}
        footer_metrics.scenario_performance.attribute_attempt_facts = [
            f
            for f in footer_metrics.scenario_performance.attribute_attempt_facts
            if f.parameter_id in filter_set
        ]
        footer_metrics.scenario_performance.attribute_scenario_facts = [
            f
            for f in footer_metrics.scenario_performance.attribute_scenario_facts
            if f.parameter_id in filter_set
        ]
        footer_metrics.scenario_stats.numeric_attempt_facts = [
            f
            for f in footer_metrics.scenario_stats.numeric_attempt_facts
            if f.parameter_id in filter_set
        ]
        footer_metrics.scenario_stats.numeric_scenario_facts = [
            f
            for f in footer_metrics.scenario_stats.numeric_scenario_facts
            if f.parameter_id in filter_set
        ]

    if request.scenario_ids:
        filter_set = {str(sid) for sid in request.scenario_ids}
        footer_metrics.scenario_simulation_performance.simulation_facts = [
            f
            for f in footer_metrics.scenario_simulation_performance.simulation_facts
            if f.scenario_id in filter_set
        ]
        footer_metrics.scenario_composition.scenario_summaries = [
            f
            for f in footer_metrics.scenario_composition.scenario_summaries
            if f.scenario_id in filter_set
        ]
        footer_metrics.scenario_composition.chat_parameter_facts = [
            f
            for f in footer_metrics.scenario_composition.chat_parameter_facts
            if f.scenario_id in filter_set
        ]

    simulations_meta = build_simulation_meta(simulations)
    scenarios_meta = build_scenario_meta(scenarios_list)
    rubrics_meta = build_rubric_meta(rubrics)
    parameters_meta = build_parameter_meta(parameters)
    fields_meta = build_field_meta(fields_list, field_parameter_map, parameters)

    if request.rubric_search:
        q = request.rubric_search.lower()
        rubrics_meta = [r for r in rubrics_meta if q in (r.get("name") or "").lower()]
    if request.simulation_picker_search:
        q = request.simulation_picker_search.lower()
        simulations_meta = [
            s for s in simulations_meta if q in (s.get("name") or "").lower()
        ]
    if request.parameter_search:
        q = request.parameter_search.lower()
        parameters_meta = [
            p for p in parameters_meta if q in (p.get("name") or "").lower()
        ]
    if request.scenario_search:
        q = request.scenario_search.lower()
        scenarios_meta = [
            s for s in scenarios_meta if q in (s.get("name") or "").lower()
        ]

    simulation_options = [
        FilterOption(value=str(s.simulation_id), label=s.name)
        for s in simulations
        if s.simulation_id and s.name
    ]

    bundle = DashboardBundleResponse(
        header_metrics=header_metrics,
        primary_metrics=primary_metrics,
        secondary_metrics=secondary_metrics,
        footer_metrics=footer_metrics,
        simulations=simulations_meta,
        scenarios=scenarios_meta,
        rubrics=rubrics_meta,
        parameters=parameters_meta,
        fields=fields_meta,
        thresholds=thresholds_dict,
        simulation_options=simulation_options,
        analytics=analytics_facets,
    )

    if target_profiles:
        tp = target_profiles[0]
        bundle.profile_name = tp.name
        bundle.profile_emails = tp.emails
        bundle.profile_primary_email = tp.primary_email

    if request.history_page_size and request.history_page_size > 0:
        profile_resource_id: UUID | None = None
        async with pool.acquire() as c:
            profile_resource_id = await c.fetchval(
                """
                SELECT profiles_id FROM profile_profiles_junction
                WHERE profile_id = $1 AND active = true
                LIMIT 1
                """,
                profile_id,
            )

        search_ctx = await resolve_dashboard_search_context(
            pool,
            redis,
            profile_resource_id=profile_resource_id,
            target_profile_id=request.target_profile_id,
            cohort_ids=request.cohort_ids,
            department_ids=request.department_ids,
            practice=request.history_practice,
            scenario_ids=request.history_scenario_ids,
            infinite_mode=request.history_infinite_mode,
            show_archived=request.history_show_archived,
            sort_by=request.history_sort_by or "date",
            sort_order=request.history_sort_order or "desc",
            page=request.history_page,
            page_size=request.history_page_size,
            date_from=parsed_start_date.date() if parsed_start_date else None,
            date_to=parsed_end_date.date() if parsed_end_date else None,
            bypass_cache=bypass_cache,
        )
        bundle.history = _build_history_response(
            search_ctx,
            practice=request.history_practice,
            simulation_search=request.history_simulation_search,
            scenario_search=request.history_scenario_search,
            profile_search=request.history_profile_search,
            page=request.history_page,
            page_size=request.history_page_size,
        )

    await set_cached(
        cache_key_val,
        {"data": bundle.model_dump(mode="json")},
        ttl=300,
        tags=tags,
        redis=redis,
    )
    return bundle, False
