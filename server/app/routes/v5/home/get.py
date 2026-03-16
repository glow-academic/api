"""Home get endpoint — simulation cards + instructional overlay.

Hardcoded home mode (practice=False). Includes instructional mode logic
for elevated roles (instructional/admin/superadmin).

Data sources:
  - home_mv: which simulations/cohorts/chats are available
  - chat_mv: per-chat config (persona_ids, rubric_ids, standard_group_ids, time_limit)
  - attempt_chat_mv: grades/stats (cohort-scoped superset for personal + instructional)
"""

import asyncio
from collections import defaultdict
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.analytics_facets import (
    HIDDEN,
    VISIBLE,
    AnalyticsFacetsConfig,
    resolve_analytics_facets,
)
from app.infra.common_context import resolve_common_context
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.home_context import resolve_home_context
from app.infra.home_permissions import (
    compute_completion_pct,
    compute_mode,
    compute_pass_pct,
    compute_status,
    compute_status_instructional,
    format_cohort_names,
)
from app.infra.auth.types import AnalyticsFilterFields
from app.infra.chat.types import (
    ChatSimulationOperational,
    RubricMapping,
    StandardGroupMapping,
    StandardMapping,
)
from app.infra.home.types import (
    GetHomeRequest,
    GetHomeResponse,
)
from app.tools.entries.attempt_chat.types import GetAttemptChatResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()

# ---------------------------------------------------------------------------
# Home analytics facets config
# ---------------------------------------------------------------------------

HOME_FACETS_CONFIG = AnalyticsFacetsConfig(
    fields=AnalyticsFilterFields(
        date_range=VISIBLE,
        departments=VISIBLE,
        cohorts=VISIBLE,
        roles=HIDDEN,
        attempts=HIDDEN,
    ),
    mv_source="profile_facts",
)

# =============================================================================
# Helpers
# =============================================================================


def _aggregate_personal_stats(
    items: list[GetAttemptChatResponse],
    profiles_resource_id: UUID,
) -> dict[UUID, dict[str, Any]]:
    """Aggregate personal profile facts by simulation_id from raw attempt_chat_mv rows."""
    stats: dict[UUID, dict[str, Any]] = {}
    seen_attempts: dict[UUID, set[UUID]] = defaultdict(set)
    for item in items:
        if not item.simulation_id or item.profile_id != profiles_resource_id:
            continue
        sim_id = item.simulation_id
        if sim_id not in stats:
            stats[sim_id] = {
                "attempt_count": 0,
                "highest_score_percent": None,
                "has_passed": False,
            }
        s = stats[sim_id]
        if item.attempt_id and item.attempt_id not in seen_attempts[sim_id]:
            seen_attempts[sim_id].add(item.attempt_id)
            s["attempt_count"] += 1
        if (
            item.grade_score is not None
            and item.grade_total_points
            and item.grade_total_points > 0
        ):
            grade_percent = float(item.grade_score) / item.grade_total_points * 100
            if (
                s["highest_score_percent"] is None
                or grade_percent > s["highest_score_percent"]
            ):
                s["highest_score_percent"] = grade_percent
        if item.grade_passed:
            s["has_passed"] = True
    return stats


def _aggregate_instructional_stats(
    facts_items: list[GetAttemptChatResponse],
    cohort_member_profiles: dict[UUID, set[UUID]],
    simulation_cohort_map: dict[UUID, list[UUID]],
) -> dict[UUID, dict[str, Any]]:
    """Per-simulation instructional stats: passed/in_progress/not_started counts."""
    best: dict[tuple[UUID, UUID], dict[str, Any]] = {}
    for item in facts_items:
        if not item.simulation_id or not item.profile_id:
            continue
        key = (item.simulation_id, item.profile_id)
        if key not in best:
            best[key] = {"has_passed": False, "has_attempted": True}
        if item.grade_passed:
            best[key]["has_passed"] = True

    result: dict[UUID, dict[str, Any]] = {}
    for sim_id, cohort_ids in simulation_cohort_map.items():
        all_members: set[UUID] = set()
        for cid in cohort_ids:
            all_members |= cohort_member_profiles.get(cid, set())
        total_members = len(all_members)

        passed_count = 0
        in_progress_count = 0
        for pid in all_members:
            attempt = best.get((sim_id, pid))
            if attempt:
                if attempt["has_passed"]:
                    passed_count += 1
                else:
                    in_progress_count += 1

        not_started_count = total_members - passed_count - in_progress_count
        completion_pct = compute_completion_pct(
            passed_count, in_progress_count, total_members
        )
        status = compute_status_instructional(
            passed_count, in_progress_count, total_members
        )

        result[sim_id] = {
            "passed_count": passed_count,
            "in_progress_count": in_progress_count,
            "not_started_count": not_started_count,
            "completion_pct": completion_pct,
            "status": status,
            "total_members": total_members,
        }
    return result


# =============================================================================
# Main internal fetch
# =============================================================================


async def get_home_internal(
    pool: asyncpg.Pool,
    profile_id: UUID,
    bypass_cache: bool = False,
) -> GetHomeResponse:
    """Dashboard-style composable context + Python assembly for simulation cards."""

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

    profile = common.profile
    profiles_resource_id = profile.profiles_id
    actor_name = profile.name
    user_role = profile.role
    view_mode = compute_mode(False, user_role)
    is_instructional = view_mode == "instructional"

    # --- Phase 1: Resolve home context + analytics facets in parallel ---
    ctx, analytics_facets = await asyncio.gather(
        resolve_home_context(
            pool,
            redis,
            profiles_resource_id=profiles_resource_id,
            bypass_cache=bypass_cache,
        ),
        resolve_analytics_facets(
            pool,
            redis,
            config=HOME_FACETS_CONFIG,
            profile=profile,
            bypass_cache=bypass_cache,
        ),
    )

    # --- Phase 2: Extract data from ArtifactContext ---
    homes = ctx.entries.get("homes", [])
    chats = ctx.entries.get("chats", [])
    attempt_chats = ctx.entries.get("attempt_chats", [])

    simulations = ctx.resources.get("simulations")
    sim_list = simulations.selected if simulations else []
    cohorts = ctx.resources.get("cohorts")
    cohort_list = cohorts.selected if cohorts else []
    personas_rp = ctx.resources.get("personas")
    persona_list = personas_rp.selected if personas_rp else []
    rubrics_rp = ctx.resources.get("rubrics")
    rubric_list = rubrics_rp.selected if rubrics_rp else []
    standard_groups_rp = ctx.resources.get("standard_groups")
    sg_list = standard_groups_rp.selected if standard_groups_rp else []
    standards_rp = ctx.resources.get("standards")
    std_list = standards_rp.selected if standards_rp else []

    # Build lookup maps
    simulation_map = {s.id: s for s in sim_list if s.id}
    persona_map = {p.id: p for p in persona_list if p.id}
    cohort_map = {c.id: c for c in cohort_list if c.id}
    rubric_map = {r.id: r for r in rubric_list if r.id}
    standard_groups_map = {sg.id: sg for sg in sg_list if sg.id}

    # Build chat_entry_id → chat lookup from chat_mv entries
    chat_map = {chat.id: chat for chat in chats}

    # Build simulation → cohort mapping from home entries
    simulation_cohort_map: dict[UUID, list[UUID]] = {}
    for h in homes:
        for sim_id in h.simulation_ids or []:
            if sim_id not in simulation_cohort_map and h.cohort_ids:
                simulation_cohort_map[sim_id] = list(h.cohort_ids)

    # --- Phase 2a: Instructional data from cohort resources ---
    cohort_member_profiles: dict[UUID, set[UUID]] | None = None
    if is_instructional:
        cohort_member_profiles = {}
        for cohort in cohort_list:
            if cohort.id and cohort.profile_ids:
                cohort_member_profiles[cohort.id] = set(cohort.profile_ids)

    # --- Phase 3: Aggregate stats ---
    personal_stats = _aggregate_personal_stats(attempt_chats, profiles_resource_id)

    instructional_stats: dict[UUID, dict[str, Any]] | None = None
    if is_instructional and cohort_member_profiles is not None:
        instructional_stats = _aggregate_instructional_stats(
            attempt_chats, cohort_member_profiles, simulation_cohort_map
        )

    # --- Phase 4: Stitch + business logic → ChatSimulationOperational ---
    items: list[ChatSimulationOperational] = []
    for h in homes:
        for sim_id in h.simulation_ids or []:
            simulation = simulation_map.get(sim_id)
            if not simulation:
                continue

            ps = personal_stats.get(sim_id, {})
            highest_score_percent = ps.get("highest_score_percent")
            has_passed = ps.get("has_passed", False)

            # Scenario IDs from simulation resource
            sim_scenario_ids = simulation.scenario_ids or []
            num_scenarios = len(sim_scenario_ids)

            # Time limits + persona color/icon from chat_mv entries
            time_limit_total_seconds = 0
            has_time_limits = False
            all_chat_persona_ids: set[UUID] = set()

            for chat_id in h.chat_ids or []:
                chat = chat_map.get(chat_id)
                if chat:
                    if chat.time_limit is not None:
                        time_limit_total_seconds += chat.time_limit
                        has_time_limits = True
                    all_chat_persona_ids.update(chat.persona_ids or [])

            time_limit_minutes = (
                round(time_limit_total_seconds / 60) if has_time_limits else None
            )

            # Persona color/icon — uniform color if all chats share one
            color: str | None = None
            icon: str | None = None
            if all_chat_persona_ids:
                unique_colors: set[str | None] = set()
                first_persona = None
                for pid in all_chat_persona_ids:
                    persona = persona_map.get(pid)
                    if persona:
                        unique_colors.add(persona.color)
                        if first_persona is None:
                            first_persona = persona
                if len(unique_colors) == 1 and first_persona:
                    color = first_persona.color
                    icon = first_persona.icon

            # Standard groups from chat_mv rubric_ids
            item_sg_ids: list[UUID] = []
            for chat_id in h.chat_ids or []:
                chat = chat_map.get(chat_id)
                if chat:
                    for rid in chat.rubric_ids or []:
                        rubric = rubric_map.get(rid)
                        if rubric and rubric.standard_group_ids:
                            item_sg_ids.extend(rubric.standard_group_ids)

            rubric_total_points = 0
            rubric_pass_points = 0
            for sgid in item_sg_ids:
                sg = standard_groups_map.get(sgid)
                if sg:
                    rubric_total_points += sg.points or 0
                    rubric_pass_points += sg.pass_points or 0

            pass_pct = compute_pass_pct(
                rubric_total_points if rubric_total_points > 0 else None,
                rubric_pass_points if rubric_pass_points > 0 else None,
            )

            cohort_titles = (
                [
                    cohort_map[cid].name
                    for cid in (h.cohort_ids or [])
                    if cid in cohort_map and cohort_map[cid].name
                ]
                if h.cohort_ids
                else None
            )
            cohort_names_junction = format_cohort_names(cohort_titles)

            highest_score = (
                round(highest_score_percent)
                if highest_score_percent is not None
                else None
            )

            standard_groups_strs = (
                [str(sg_id) for sg_id in item_sg_ids] if item_sg_ids else None
            )

            chat_entry_id = h.chat_ids[0] if h.chat_ids else None
            home_id = h.id

            attempt_count = ps.get("attempt_count", 0)
            if is_instructional and instructional_stats is not None:
                ist = instructional_stats.get(sim_id, {})
                status = ist.get("status", "not-started")
                completion_pct = ist.get("completion_pct", 0)
                passed_count = ist.get("passed_count", 0)
                in_progress_count = ist.get("in_progress_count", 0)
                not_started_count = ist.get("not_started_count", 0)
            else:
                status = compute_status(has_passed, attempt_count)
                completion_pct = None
                passed_count = None
                in_progress_count = None
                not_started_count = None

            items.append(
                ChatSimulationOperational(
                    simulation_id=sim_id,
                    simulation_name=simulation.name,
                    simulation_description=simulation.description,
                    time_limit=time_limit_minutes,
                    chat_entry_id=chat_entry_id,
                    home_id=home_id,
                    scenario_ids=sim_scenario_ids or None,
                    cohort_ids=list(h.cohort_ids) if h.cohort_ids else None,
                    color=color,
                    icon=icon,
                    view_mode=view_mode,
                    num_sessions=num_scenarios,
                    highest_score=highest_score,
                    has_passed=has_passed,
                    status=status,
                    pass_pct=pass_pct,
                    cohort_names_junction=cohort_names_junction,
                    standard_groups=standard_groups_strs,
                    practice_simulation=None,
                    completion_pct=completion_pct,
                    passed_count=passed_count,
                    in_progress_count=in_progress_count,
                    not_started_count=not_started_count,
                )
            )

    # Build rubric mappings
    rubrics: list[RubricMapping] | None = None
    if rubric_list:
        rubrics = [
            RubricMapping(
                rubric_id=r.id,
                name=r.name,
                standard_group_ids=(
                    [str(sg_id) for sg_id in r.standard_group_ids]
                    if r.standard_group_ids
                    else None
                ),
            )
            for r in rubric_list
            if r.id
        ]

    standard_groups: list[StandardGroupMapping] | None = None
    if sg_list:
        standard_groups = [
            StandardGroupMapping(
                standard_group_id=sg.id,
                name=sg.name,
                description=sg.description,
                points=sg.points,
                pass_points=sg.pass_points,
            )
            for sg in sg_list
            if sg.id
        ]

    standards: list[StandardMapping] | None = None
    if std_list:
        standards = [
            StandardMapping(
                standard_id=st.id,
                standard_group_id=st.standard_group_id,
                name=st.name,
                description=st.description,
                points=st.points,
            )
            for st in std_list
            if st.id
        ]

    return GetHomeResponse(
        actor_name=actor_name,
        items=items,
        rubrics=rubrics,
        standard_groups=standard_groups,
        standards=standards,
        analytics=analytics_facets,
    )


# =============================================================================
# Route handler
# =============================================================================


@router.post("/get", response_model=GetHomeResponse)
async def home_get(
    request: GetHomeRequest,
    http_request: Request,
    response: Response,
) -> GetHomeResponse:
    """Get simulations available for home (operational)."""
    tags = ["home", "get"]
    bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"

    cache_key_val = cache_key(
        http_request.url.path,
        request.model_dump(mode="json"),
    )

    if not bypass_cache:
        cached = await get_cached(cache_key_val, redis=get_redis_client())
        if cached:
            response.headers["X-Cache-Tags"] = ",".join(tags)
            response.headers["X-Cache-Hit"] = "1"
            return GetHomeResponse.model_validate(cached["data"])

    sql_query: str | None = None
    sql_params: tuple[Any, ...] | None = None

    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        if not pool:
            raise RuntimeError("Database pool not initialized")

        async def _runner() -> GetHomeResponse:
            api_response = await get_home_internal(
                pool=pool,
                profile_id=profile_id,
                bypass_cache=bypass_cache,
            )

            profile_specific_tags = tags + [f"home:profile:{profile_id}"]
            await set_cached(
                cache_key_val,
                {"data": api_response.model_dump(mode="json")},
                ttl=300,
                tags=profile_specific_tags,
                redis=get_redis_client(),
            )
            response.headers["X-Cache-Tags"] = ",".join(tags)
            response.headers["X-Cache-Hit"] = "0"
            return api_response

        return await run_artifact_operation_with_audit(
            pool,
            get_redis_client(),
            artifact="home",
            profile_id=profile_id,
            session_id=http_request.state.session_id,
            operation="get",
            arguments=request.model_dump(mode="json"),
            bypass_cache=bypass_cache,
            response_model=GetHomeResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="home_get",
            sql_query=sql_query,
            sql_params=sql_params,
            request=http_request,
        )
