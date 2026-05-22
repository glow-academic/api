"""Canonical shared scenario GET operation."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.group.resolve import resolve_group_impl
from app.infra.persona.types import SectionFilter
from app.infra.scenario.context import resolve_scenario_context
from app.infra.scenario.permissions import SCENARIO_RESOURCES, has_access
from app.infra.scenario.permissions_context import resolve_scenario_permissions_context
from app.infra.scenario.sections import build_scenario_get_result
from app.infra.scenario.types import GetScenarioApiResponse
from app.infra.server_timing import timed
from app.infra.tool_graph import score_tools

SECTIONS = [
    "names", "descriptions", "problem_statements", "flags", "departments",
    "personas", "documents", "parameters", "parameter_fields",
    "objectives", "images", "videos", "questions", "options",
]


def _sf(filters: dict[str, SectionFilter | None], section: str, attr: str, default=None):
    """Get a SectionFilter attribute for a section, with default."""
    sf = filters.get(section)
    if sf is None:
        return default
    return getattr(sf, attr, default)


async def get_scenario_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    filters: dict[str, SectionFilter | None] | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> GetScenarioApiResponse:
    """Resolve the canonical scenario artifact bundle for any surface."""
    f = filters or {}
    scenario_id = id  # alias: tools send 'id', internal code uses 'scenario_id'

    # Extract parameter_ids from parameter_fields filter
    pf_filter = f.get("parameter_fields")
    raw_param_ids = pf_filter.parameter_ids if pf_filter and pf_filter.parameter_ids else None
    parameter_ids = [UUID(pid) if isinstance(pid, str) else pid for pid in raw_param_ids] if raw_param_ids else None

    with timed("common"):
        common = await resolve_common_context(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            bypass_cache=bypass_cache,
        )
    if common is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    if group_id is None:
        with timed("group"):
            _gr = await resolve_group_impl(
                pool, redis,
                artifact_type="scenario",
                profile_id=profile_id,
                session_id=session_id,
                include_history=False,
            )
            group_id = _gr.group_id
    effective_group_id = group_id
    perms = None
    if scenario_id is not None:
        with timed("permissions"):
            perms = await resolve_scenario_permissions_context(pool, scenario_id)
        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Scenario {scenario_id} not found",
            )
        if not has_access(
            common.profile.role_level,
            common.profile.department_ids,
            perms.department_ids,
        ):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this scenario. "
                "It may be restricted to other departments.",
            )

    with timed("scenario_ctx"):
        scenario = await resolve_scenario_context(
        pool,
        redis,
        scenario_id=scenario_id,
        group_id=effective_group_id,
        draft_id=draft_id,
        user_department_ids=common.profile.department_ids,
        parameter_ids=parameter_ids,
        description_search=_sf(f, "descriptions", "search"),
        persona_search=_sf(f, "personas", "search"),
        document_search=_sf(f, "documents", "search"),
        parameter_search=_sf(f, "parameters", "search"),
        problem_statement_search=_sf(f, "problem_statements", "search"),
        image_search=_sf(f, "images", "search"),
        video_search=_sf(f, "videos", "search"),
        question_search=_sf(f, "questions", "search"),
        option_search=_sf(f, "options", "search"),
        persona_show_selected=_sf(f, "personas", "selected"),
        document_show_selected=_sf(f, "documents", "selected"),
        parameter_show_selected=_sf(f, "parameters", "selected"),
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, SCENARIO_RESOURCES)

    include = {s: _sf(f, s, "include") is not False for s in SECTIONS}
    selected_only = {s: _sf(f, s, "selected") or False for s in SECTIONS}
    suggested_only = {s: _sf(f, s, "suggested") or False for s in SECTIONS}

    with timed("build"):
      return build_scenario_get_result(
        common=common,
        scenario=scenario,
        scores=scores,
        perms=perms,
        group_id=effective_group_id,
        video_enabled=_sf(f, "videos", "include"),
        images_enabled=_sf(f, "images", "include"),
        objectives_enabled=_sf(f, "objectives", "include"),
        questions_enabled=_sf(f, "questions", "include"),
        problem_statement_enabled=_sf(f, "problem_statements", "include"),
        include=include,
        selected_only=selected_only,
        suggested_only=suggested_only,
    )
