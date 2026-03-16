"""Home search endpoint — paginated attempt history.

Data sources:
  - attempt_mv: paginated attempts (filtered by profile, practice=False)
  - attempt_chat_mv: per-attempt grades for aggregation
  - Resources: simulations, personas, scenarios, profiles (display names)
"""

from collections import defaultdict
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.common_context import resolve_common_context
from app.infra.globals import get_pool, get_redis_client
from app.infra.home_context import resolve_home_search_context
from app.infra.home_permissions import (
    compute_pass_pct,
    compute_score_status,
    compute_show_continue,
    compute_show_view,
)
from app.infra.home.types import (
    ListHomeRequest,
    ListHomeResponse,
)
from app.infra.v5_types import (
    FilterOption,
    HistoryItem,
)
from app.tools.entries.attempt_chat.types import GetAttemptChatResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()

# =============================================================================
# Helpers
# =============================================================================


def _compute_history_aggregates(
    chats: list[GetAttemptChatResponse],
) -> dict[str, Any]:
    """Compute attempt-level aggregates from attempt_chat_mv rows."""
    num_chats = len(chats)
    num_chats_completed = sum(1 for c in chats if c.completed)

    scenario_ids_set: set[UUID] = set()
    completed_scenario_ids: set[UUID] = set()
    persona_ids_set: set[UUID] = set()

    total_score = 0.0
    total_possible = 0.0
    has_passed = False
    total_time_seconds = 0
    rubric_total_points: int | None = None
    rubric_pass_points: int | None = None

    for chat in chats:
        if chat.scenario_id:
            scenario_ids_set.add(chat.scenario_id)
            if chat.completed:
                completed_scenario_ids.add(chat.scenario_id)
        if chat.persona_ids:
            persona_ids_set.update(chat.persona_ids)

        if chat.grade_score is not None and chat.grade_total_points:
            total_score += chat.grade_score
            total_possible += chat.grade_total_points
        if chat.grade_passed:
            has_passed = True
        if chat.grade_time_taken is not None:
            total_time_seconds += chat.grade_time_taken
        if chat.grade_total_points is not None:
            rubric_total_points = (rubric_total_points or 0) + chat.grade_total_points
        if chat.grade_pass_points is not None:
            rubric_pass_points = (rubric_pass_points or 0) + chat.grade_pass_points

    score_percent: float | None = None
    if total_possible > 0:
        score_percent = round((total_score / total_possible) * 100, 2)

    return {
        "num_scenarios": len(scenario_ids_set),
        "num_scenarios_completed": len(completed_scenario_ids),
        "num_chats": num_chats,
        "num_chats_completed": num_chats_completed,
        "score_percent": score_percent,
        "has_passed": has_passed,
        "total_time_seconds": total_time_seconds,
        "rubric_total_points": rubric_total_points,
        "rubric_pass_points": rubric_pass_points,
        "persona_ids": list(persona_ids_set) if persona_ids_set else None,
        "scenario_ids": list(scenario_ids_set) if scenario_ids_set else None,
    }


def _transform_history_item(
    attempt: Any,
    aggregates: dict[str, Any],
    resource_meta: dict[str, dict[UUID, dict[str, Any]]],
    pass_threshold: float | None,
) -> HistoryItem:
    """Transform an attempt MV row + aggregates into a HistoryItem."""
    sim_meta = (
        resource_meta["simulations"].get(attempt.simulation_id, {})
        if attempt.simulation_id
        else {}
    )
    simulation_name = sim_meta.get("name")

    profile_meta = (
        resource_meta["profiles"].get(attempt.profile_id, {})
        if attempt.profile_id
        else {}
    )
    profile_name = profile_meta.get("name")

    persona_names: list[str] = []
    persona_colors: list[str] = []
    persona_ids = aggregates.get("persona_ids")
    if persona_ids:
        for pid in persona_ids:
            p_meta = resource_meta["personas"].get(pid, {})
            if p_meta.get("name"):
                persona_names.append(p_meta["name"])
            if p_meta.get("color"):
                persona_colors.append(p_meta["color"])

    scenario_titles: list[str] = []
    scenario_ids = aggregates.get("scenario_ids") or (
        list(attempt.scenario_ids) if attempt.scenario_ids else None
    )
    if scenario_ids:
        for sid in scenario_ids:
            s_meta = resource_meta["scenarios"].get(sid, {})
            if s_meta.get("name"):
                scenario_titles.append(s_meta["name"])

    score_percent = aggregates.get("score_percent")
    pass_pct = compute_pass_pct(
        aggregates.get("rubric_total_points"), aggregates.get("rubric_pass_points")
    )
    score_status = compute_score_status(score_percent, pass_threshold)
    score = round(score_percent) if score_percent is not None else None

    show_view = compute_show_view(False)
    num_incomplete_chats = (aggregates.get("num_chats") or 0) - (
        aggregates.get("num_chats_completed") or 0
    )
    show_continue = compute_show_continue(
        is_archived=False,
        infinite_mode=attempt.infinite_mode,
        num_scenarios=aggregates.get("num_scenarios"),
        num_scenarios_completed=aggregates.get("num_scenarios_completed"),
        time_limit_seconds=None,
        elapsed_seconds=aggregates.get("total_time_seconds"),
        num_incomplete_chats=num_incomplete_chats,
    )

    department_ids = [str(attempt.department_id)] if attempt.department_id else None

    return HistoryItem(
        attempt_id=attempt.attempt_id,
        date=(
            attempt.attempt_created_at.isoformat()
            if attempt.attempt_created_at
            else None
        ),
        profile_id=attempt.profile_id,
        profile_name=profile_name,
        simulation_id=attempt.simulation_id,
        simulation_name=simulation_name,
        num_scenarios=aggregates.get("num_scenarios"),
        num_scenarios_completed=aggregates.get("num_scenarios_completed"),
        infinite_mode=attempt.infinite_mode,
        time_limit=None,
        persona_names_junction=persona_names if persona_names else None,
        persona_colors_junction=persona_colors if persona_colors else None,
        scenario_ids=scenario_ids,
        scenario_titles=scenario_titles if scenario_titles else None,
        department_ids=department_ids,
        score=score,
        score_status=score_status,
        pass_pct=pass_pct,
        show_view=show_view,
        show_continue=show_continue,
        is_archived=None,
        practice_simulation=None,
        practice_scenario_id=None,
    )


# =============================================================================
# Main internal fetch
# =============================================================================


async def list_home_internal(
    pool: asyncpg.Pool,
    request: ListHomeRequest,
    profile_id: UUID,
    bypass_cache: bool = False,
) -> ListHomeResponse:
    """Paginated attempt history from raw MVs + resource hydration."""

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

    profiles_resource_id = common.profile.profiles_id

    # --- Phase 1: Resolve search context ---
    ctx = await resolve_home_search_context(
        pool,
        redis,
        profiles_resource_id=profiles_resource_id,
        scenario_ids=request.scenario_ids,
        infinite_mode=request.infinite_mode,
        sort_order=request.sort_order or "desc",
        page=request.page,
        page_size=request.page_size,
        bypass_cache=bypass_cache,
    )

    # --- Phase 2: Extract data ---
    attempts = ctx.entries.get("attempts", [])
    attempt_chats = ctx.entries.get("attempt_chats", [])
    total_attempts = ctx.entries.get("total_attempts", [])

    simulations = ctx.resources.get("simulations")
    sim_list = simulations.selected if simulations else []
    profiles_rp = ctx.resources.get("profiles")
    profile_list = profiles_rp.selected if profiles_rp else []
    personas_rp = ctx.resources.get("personas")
    persona_list = personas_rp.selected if personas_rp else []
    scenarios_rp = ctx.resources.get("scenarios")
    scenario_list = scenarios_rp.selected if scenarios_rp else []

    # Build resource meta maps
    resource_meta: dict[str, dict[UUID, dict[str, Any]]] = {
        "simulations": {},
        "profiles": {},
        "personas": {},
        "scenarios": {},
    }
    for s in sim_list:
        if s.id:
            resource_meta["simulations"][s.id] = {"name": s.name}
    for p in profile_list:
        if p.id:
            resource_meta["profiles"][p.id] = {"name": p.name}
    for p in persona_list:
        if p.id:
            resource_meta["personas"][p.id] = {"name": p.name, "color": p.color}
    for s in scenario_list:
        if s.id:
            resource_meta["scenarios"][s.id] = {"name": s.name}

    # --- Phase 3: Group chats by attempt_id + compute aggregates ---
    chats_by_attempt: dict[UUID, list[GetAttemptChatResponse]] = defaultdict(list)
    for ac in attempt_chats:
        if ac.attempt_id:
            chats_by_attempt[ac.attempt_id].append(ac)

    pass_threshold = 70.0

    history_items: list[HistoryItem] = []
    for attempt in attempts:
        attempt_chats_list = chats_by_attempt.get(attempt.attempt_id, [])
        agg = _compute_history_aggregates(attempt_chats_list)
        history_items.append(
            _transform_history_item(attempt, agg, resource_meta, pass_threshold)
        )

    # --- Phase 4: Build filter options from total_attempts ---
    sim_option_counts: dict[UUID, int] = {}
    scenario_option_counts: dict[UUID, int] = {}
    for a in total_attempts:
        if a.simulation_id:
            sim_option_counts[a.simulation_id] = (
                sim_option_counts.get(a.simulation_id, 0) + 1
            )
        for sid in a.scenario_ids or []:
            scenario_option_counts[sid] = scenario_option_counts.get(sid, 0) + 1

    simulation_options: list[FilterOption] = []
    for sim_id, count in sim_option_counts.items():
        label = resource_meta["simulations"].get(sim_id, {}).get("name") or str(sim_id)
        simulation_options.append(
            FilterOption(value=str(sim_id), label=label, count=count)
        )
    if request.simulation_search:
        q = request.simulation_search.lower()
        simulation_options = [
            o for o in simulation_options if q in (o.label or "").lower()
        ]

    scenario_options: list[FilterOption] = []
    for scn_id, count in scenario_option_counts.items():
        label = resource_meta["scenarios"].get(scn_id, {}).get("name") or str(scn_id)
        scenario_options.append(
            FilterOption(value=str(scn_id), label=label, count=count)
        )
    if request.scenario_search:
        q = request.scenario_search.lower()
        scenario_options = [o for o in scenario_options if q in (o.label or "").lower()]

    total_count = len(total_attempts)
    page_size = request.page_size
    total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0

    return ListHomeResponse(
        data=history_items,
        total_count=total_count,
        page=request.page,
        page_size=page_size,
        total_pages=total_pages,
        simulation_options=simulation_options or None,
        scenario_options=scenario_options or None,
    )


# =============================================================================
# Route handler
# =============================================================================


@router.post("/search", response_model=ListHomeResponse)
async def search_home(
    request: ListHomeRequest,
    http_request: Request,
    response: Response,
) -> ListHomeResponse:
    """Get paginated attempt history for home."""
    tags = ["home", "list"]
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
            return ListHomeResponse.model_validate(cached["data"])

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

        api_response = await list_home_internal(
            pool=pool,
            request=request,
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

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="home_search",
            sql_query=sql_query,
            sql_params=sql_params,
            request=http_request,
        )
