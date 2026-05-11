"""Dashboard artifact — search endpoint (attempt history, paginated).

Composable pattern: resolve_common_context → resolve_dashboard_search_context → Python assembly.
"""

from collections import defaultdict
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.api_types import FilterOption, HistoryItem, HistoryResponse
from app.infra.attempt.chat.permissions import (
    compute_pass_pct,
    compute_score_status,
    compute_show_continue,
    compute_show_view,
)
from app.infra.common_context import resolve_common_context
from app.infra.dashboard.context import resolve_dashboard_search_context
from app.infra.dashboard.types import (
    ListDashboardRequest,
)
from app.infra.dashboard.visibility import resolve_visible_profile_ids
from app.infra.globals import get_pool, get_redis_client
from app.infra.types import ArtifactContext
from app.tools.entries.attempt_chat.types import GetAttemptChatResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


# ---------------------------------------------------------------------------
# Pure Python helpers
# ---------------------------------------------------------------------------


def _compute_history_aggregates(chats: list[GetAttemptChatResponse]) -> dict[str, Any]:
    """Compute attempt-level aggregates from chat view items."""
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
    practice: bool | None,
) -> HistoryItem:
    """Transform an attempt MV row + aggregates into a HistoryItem."""
    sim_meta = (
        resource_meta["simulations"].get(attempt.simulation_id, {})
        if attempt.simulation_id
        else {}
    )
    simulation_name = sim_meta.get("name")
    time_limit = sim_meta.get("time_limit")

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

    is_practice_view = practice is True
    is_archived = attempt.is_archived if is_practice_view else False
    show_view = compute_show_view(is_archived)
    num_incomplete_chats = (aggregates.get("num_chats") or 0) - (
        aggregates.get("num_chats_completed") or 0
    )
    show_continue = compute_show_continue(
        is_archived=is_archived,
        infinite_mode=attempt.infinite_mode,
        num_scenarios=aggregates.get("num_scenarios"),
        num_scenarios_completed=aggregates.get("num_scenarios_completed"),
        time_limit_seconds=time_limit,
        elapsed_seconds=aggregates.get("total_time_seconds"),
        num_incomplete_chats=num_incomplete_chats,
    )

    department_ids = [str(attempt.department_id)] if attempt.department_id else None
    practice_scenario_id = scenario_ids[0] if scenario_ids else None

    return HistoryItem(
        attempt_id=attempt.attempt_id,
        date=attempt.attempt_created_at.isoformat() if attempt.attempt_created_at else None,
        profile_id=attempt.profile_id,
        profile_name=profile_name,
        simulation_id=attempt.simulation_id,
        simulation_name=simulation_name,
        num_scenarios=aggregates.get("num_scenarios"),
        num_scenarios_completed=aggregates.get("num_scenarios_completed"),
        infinite_mode=attempt.infinite_mode,
        time_limit=time_limit,
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
        is_archived=is_archived if is_practice_view else None,
        practice_simulation=True if is_practice_view else None,
        practice_scenario_id=practice_scenario_id if is_practice_view else None,
    )


def _build_history_response(
    ctx: ArtifactContext,
    *,
    practice: bool | None = None,
    simulation_search: str | None = None,
    scenario_search: str | None = None,
    profile_search: str | None = None,
    page: int = 0,
    page_size: int = 20,
) -> HistoryResponse:
    """Build HistoryResponse from search context — pure Python assembly."""
    attempts = ctx.entries.get("attempts", [])
    chats = ctx.entries.get("attempt_chats", [])
    total_count = ctx.entries.get("total_count", 0)

    simulations_rp = ctx.resources.get("simulations")
    h_sims = simulations_rp.selected if simulations_rp else []
    scenarios_rp = ctx.resources.get("scenarios")
    h_scens = scenarios_rp.selected if scenarios_rp else []
    personas_rp = ctx.resources.get("personas")
    h_pers = personas_rp.selected if personas_rp else []
    profiles_rp = ctx.resources.get("profiles")
    h_profs = profiles_rp.selected if profiles_rp else []

    pass_threshold = 70.0

    # Group chats by attempt
    chats_by_attempt: dict[UUID, list[GetAttemptChatResponse]] = defaultdict(list)
    for chat in chats:
        if chat.attempt_id:
            chats_by_attempt[chat.attempt_id].append(chat)

    # Compute aggregates
    aggregates_by_attempt: dict[UUID, dict[str, Any]] = {}
    for item in attempts:
        attempt_chats = chats_by_attempt.get(item.attempt_id, [])
        aggregates_by_attempt[item.attempt_id] = _compute_history_aggregates(
            attempt_chats
        )

    # Build resource meta maps
    resource_meta: dict[str, dict[UUID, dict[str, Any]]] = {
        "simulations": {},
        "profiles": {},
        "personas": {},
        "scenarios": {},
    }
    # All four resource Get*Response types expose the canonical id
    # as `id` (Get{Simulation,Profile,Persona,Scenario}Response).
    # Pre-fix this loop accessed namespaced fields (.simulation_id,
    # .profile_id, .persona_id, .scenario_id) that don't exist —
    # latent until the analytical seed populated h_*'s.
    for s in h_sims:
        if s.id:
            resource_meta["simulations"][s.id] = {
                "name": s.name,
                "time_limit": None,
            }
    for p in h_profs:
        if p.id:
            resource_meta["profiles"][p.id] = {"name": p.name}
    for p in h_pers:
        if p.id:
            resource_meta["personas"][p.id] = {
                "name": p.name,
                "color": p.color,
            }
    for s in h_scens:
        if s.id:
            resource_meta["scenarios"][s.id] = {"name": s.name}

    # Transform attempts
    history_items = [
        _transform_history_item(
            item,
            aggregates_by_attempt.get(item.attempt_id, {}),
            resource_meta,
            pass_threshold,
            practice,
        )
        for item in attempts
    ]

    simulation_options = sorted(
        [
            FilterOption(value=str(s.id), label=s.name)
            for s in h_sims
            if s.id and s.name
        ],
        key=lambda option: option.label.lower(),
    )
    scenario_options = sorted(
        [
            FilterOption(value=str(s.id), label=s.name)
            for s in h_scens
            if s.id and s.name
        ],
        key=lambda option: option.label.lower(),
    )
    profile_options = sorted(
        [
            FilterOption(value=str(p.id), label=p.name)
            for p in h_profs
            if p.id and p.name
        ],
        key=lambda option: option.label.lower(),
    )
    total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0

    return HistoryResponse(
        data=history_items,
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        simulation_options=simulation_options,
        scenario_options=scenario_options,
        profile_options=profile_options,
    )


# ---------------------------------------------------------------------------
# Route handler
# ---------------------------------------------------------------------------


@router.post("/search", response_model=HistoryResponse)
async def search_dashboard(
    request: ListDashboardRequest,
    http_request: Request,
    response: Response,
) -> HistoryResponse:
    """Get dashboard attempt history (paginated)."""
    tags = ["artifacts", "dashboard", "list"]
    bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"

    profile_id = http_request.state.profile_id
    cache_key_val = cache_key(
        http_request.url.path,
        {
            "profile_id": str(profile_id) if profile_id else None,
            "request": request.model_dump(mode="json"),
        },
    )

    if not bypass_cache:
        cached = await get_cached(cache_key_val, redis=get_redis_client())
        if cached:
            response.headers["X-Cache-Tags"] = ",".join(tags)
            response.headers["X-Cache-Hit"] = "1"
            return HistoryResponse.model_validate(cached["data"])

    try:
        pool = get_pool()
        if not pool:
            raise RuntimeError("Database pool not initialized")

        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        redis = get_redis_client()

        # --- Phase 0: Resolve common context ---
        common = await resolve_common_context(
            pool, redis, profile_id=profile_id, bypass_cache=bypass_cache
        )
        if not common:
            raise HTTPException(status_code=401, detail="Profile not found")

        visible_profile_ids = await resolve_visible_profile_ids(pool, common.profile)

        # If client supplied profile_ids filter, intersect with visible set so
        # callers can never widen the visibility scope by guessing profile UUIDs.
        scoped_profile_ids: list[UUID] | None = visible_profile_ids
        if request.profile_ids and visible_profile_ids is not None:
            visible_set = set(visible_profile_ids)
            scoped_profile_ids = [pid for pid in request.profile_ids if pid in visible_set]

        # Parse dates
        date_from = None
        date_to = None
        if request.start_date:
            date_from = datetime.fromisoformat(
                request.start_date.replace("Z", "+00:00")
            ).date()
        if request.end_date:
            date_to = datetime.fromisoformat(
                request.end_date.replace("Z", "+00:00")
            ).date()

        # --- Phase 1: Resolve dashboard search context ---
        ctx = await resolve_dashboard_search_context(
            pool,
            redis,
            profile_resource_ids=scoped_profile_ids,
            target_profile_id=request.target_profile_id,
            cohort_ids=request.cohort_ids,
            department_ids=request.department_ids,
            role_ids=request.role_ids,
            practice=request.practice,
            scenario_ids=request.scenario_ids,
            simulation_ids=request.simulation_ids,
            infinite_mode=request.infinite_mode,
            show_archived=request.show_archived,
            sort_by=request.sort_by,
            sort_order=request.sort_order,
            page=request.page,
            page_size=request.page_size,
            date_from=date_from,
            date_to=date_to,
            bypass_cache=bypass_cache,
        )

        # --- Phase 2: Pure Python assembly ---
        api_response = _build_history_response(
            ctx,
            practice=request.practice,
            simulation_search=request.simulation_search,
            scenario_search=request.scenario_search,
            profile_search=request.profile_search,
            page=request.page,
            page_size=request.page_size,
        )

        await set_cached(
            cache_key_val,
            {"data": api_response.model_dump(mode="json")},
            ttl=300,
            tags=tags,
            redis=redis,
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
            operation="dashboard_search",
            request=http_request,
        )
