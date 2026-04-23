"""Canonical shared record get operations — profile report dashboard.

Scoped dashboard: metrics for a single target profile. Mirrors the
``dashboard``/``leaderboard``/``activity`` shape — cached impl takes a
request object, canonical impl takes kwargs.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException

from app.infra.api_types import FilterOption
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
from app.infra.dashboard.types import DashboardBundleResponse
from app.infra.globals import get_redis_client
from app.infra.record.types import RecordRequest
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_record_impl_cached(
    pool,
    request: RecordRequest,
    *,
    profile_id: UUID,
    bypass_cache: bool = False,
    cache_key_path: str = "/record/get",
) -> tuple[DashboardBundleResponse, bool]:
    """Compute the record profile-report bundle. Cached on the request shape.

    Returns ``(bundle, cache_hit)`` — same contract as the other dashboards.
    """
    tags = ["artifacts", "record", "views", "analytics"]
    cache_key_val = cache_key(cache_key_path, request.model_dump(mode="json"))

    if not bypass_cache:
        cached = await get_cached(cache_key_val, redis=get_redis_client())
        if cached:
            return DashboardBundleResponse.model_validate(cached["data"]), True

    redis = get_redis_client()

    # --- Phase 0: Resolve common context (profile identity) ---
    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        bypass_cache=bypass_cache,
    )
    if not common:
        raise HTTPException(status_code=401, detail="Profile not found")

    # --- Phase 1: Parse filters ---
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

    # --- Phase 2: Resolve dashboard context (scoped to target profile) ---
    ctx = await resolve_dashboard_context(
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
    )

    # --- Phase 3: Extract data from context ---
    chat_items = ctx.entries.get("chat_items", [])
    rubric_items = ctx.entries.get("rubric_items", [])
    thresholds_list = ctx.entries.get("thresholds", [])
    scenario_count_rows = ctx.entries.get("scenario_counts", [])
    cohort_name_rows = ctx.entries.get("cohort_names", [])

    simulations_rp = ctx.resources.get("simulations")
    simulations = simulations_rp.selected if simulations_rp else []
    scenarios_rp = ctx.resources.get("scenarios")
    scenarios_list = scenarios_rp.selected if scenarios_rp else []
    personas_rp = ctx.resources.get("personas")
    personas = personas_rp.selected if personas_rp else []
    rubrics_rp = ctx.resources.get("rubrics")
    rubrics = rubrics_rp.selected if rubrics_rp else []
    standard_groups_rp = ctx.resources.get("standard_groups")
    standard_groups = standard_groups_rp.selected if standard_groups_rp else []
    documents_rp = ctx.resources.get("documents")
    documents = documents_rp.selected if documents_rp else []
    pf_rp = ctx.resources.get("parameter_fields")
    parameter_fields = pf_rp.selected if pf_rp else []
    params_rp = ctx.resources.get("parameters")
    parameters = params_rp.selected if params_rp else []
    fields_rp = ctx.resources.get("fields")
    fields_list = fields_rp.selected if fields_rp else []
    profiles_rp = ctx.resources.get("profiles")
    target_profiles = profiles_rp.selected if profiles_rp else []

    thresholds_dict = (
        thresholds_list[0]
        if thresholds_list
        else {"success": 85, "warning": 80, "danger": 70}
    )

    # --- Phase 4: Build name maps ---
    simulation_scenario_counts = {
        str(r["simulation_id"]): r["scenario_count"] for r in scenario_count_rows
    }
    persona_name_map: dict[str, str] = {
        str(p.persona_id): p.name for p in personas if p.persona_id and p.name
    }
    cohort_name_map: dict[str, str] = {
        str(r["id"]): r["name"]
        for r in cohort_name_rows
        if r["id"] and r["name"]
    }
    simulation_name_map: dict[str, str] = {
        str(s.simulation_id): s.name
        for s in simulations
        if s.simulation_id and s.name
    }
    scenario_name_map: dict[str, str] = {
        str(s.scenario_id): s.name
        for s in scenarios_list
        if s.scenario_id and s.name
    }
    standard_group_name_map: dict[str, str] = {
        str(getattr(sg, "standard_group_id", None)): getattr(sg, "name", "")
        for sg in standard_groups
        if getattr(sg, "standard_group_id", None) and getattr(sg, "name", None)
    }
    field_parameter_map: dict[UUID, UUID] = {}
    for pf in parameter_fields:
        if pf.field_id and pf.parameter_id:
            field_parameter_map[pf.field_id] = pf.parameter_id

    # --- Phase 5: Compute all 4 metric sections ---
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

    # --- Phase 5b: Apply picker filters ---
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

    # --- Phase 6: Build metadata lists ---
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
        FilterOption(
            value=str(item.simulation_id) if item.simulation_id else "",
            label=item.name,
        )
        for item in simulations
        if item.simulation_id
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
    )

    if target_profiles:
        tp = target_profiles[0]
        bundle.profile_name = tp.name
        bundle.profile_emails = tp.emails
        bundle.profile_primary_email = tp.primary_email

    # --- Phase 7: Inline history (backward compat) ---
    if request.history_page_size and request.history_page_size > 0:
        # Local import — route module depends on this one, so pulling
        # `_build_history_response` in at module load would cycle.
        from app.routes.attempt.dashboard.search import _build_history_response

        async with pool.acquire() as c:
            profile_resource_id: UUID | None = await c.fetchval(
                """
                SELECT profiles_id FROM profile_profiles_junction
                WHERE profile_id = $1 AND active = true
                LIMIT 1
                """,
                profile_id,
            )

        date_from = parsed_start_date.date() if parsed_start_date else None
        date_to = parsed_end_date.date() if parsed_end_date else None

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
            date_from=date_from,
            date_to=date_to,
            bypass_cache=bypass_cache,
        )

        history_result = _build_history_response(
            search_ctx,
            practice=request.history_practice,
            simulation_search=request.history_simulation_search,
            scenario_search=request.history_scenario_search,
            page=request.history_page,
            page_size=request.history_page_size,
        )
        bundle.history = history_result

    await set_cached(
        cache_key_val,
        {"data": bundle.model_dump(mode="json")},
        ttl=300,
        tags=tags,
        redis=redis,
    )
    return bundle, False


async def get_record_impl(
    pool,
    redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    bypass_cache: bool = False,
    **filters,
) -> DashboardBundleResponse:
    """Canonical kwargs entry point — wraps ``get_record_impl_cached``."""
    request = RecordRequest(**filters)
    bundle, _cache_hit = await get_record_impl_cached(
        pool,
        request,
        profile_id=profile_id,
        bypass_cache=bypass_cache,
        cache_key_path="/record/get",
    )
    return bundle
