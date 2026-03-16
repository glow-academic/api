"""Canonical shared scenario GET operation."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.scenario.context import resolve_scenario_context
from app.infra.scenario.permissions import SCENARIO_RESOURCES, has_access
from app.infra.scenario.permissions_context import resolve_scenario_permissions_context
from app.infra.scenario.sections import build_scenario_get_result
from app.infra.tool_graph import score_tools
from app.infra.scenario.types import GetScenarioApiResponse


async def get_scenario_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    scenario_id: UUID | None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    parameter_ids: list[UUID] | None = None,
    description_search: str | None = None,
    persona_search: str | None = None,
    document_search: str | None = None,
    parameter_search: str | None = None,
    problem_statement_search: str | None = None,
    image_search: str | None = None,
    video_search: str | None = None,
    question_search: str | None = None,
    option_search: str | None = None,
    persona_show_selected: bool | None = None,
    document_show_selected: bool | None = None,
    parameter_show_selected: bool | None = None,
    bypass_cache: bool = False,
) -> GetScenarioApiResponse:
    """Resolve the canonical scenario artifact bundle for any surface."""
    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        draft_id=draft_id,
        artifact_type="scenario",
        bypass_cache=bypass_cache,
    )
    if common is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    effective_group_id = group_id or common.profile.group_id

    perms = None
    if scenario_id is not None:
        perms = await resolve_scenario_permissions_context(pool, scenario_id)
        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Scenario {scenario_id} not found",
            )
        if not has_access(
            common.profile.role,
            common.profile.department_ids,
            perms.department_ids,
        ):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this scenario. "
                "It may be restricted to other departments.",
            )

    scenario = await resolve_scenario_context(
        pool,
        redis,
        scenario_id=scenario_id,
        group_id=effective_group_id,
        draft_id=draft_id,
        user_department_ids=common.profile.department_ids,
        parameter_ids=parameter_ids,
        description_search=description_search,
        persona_search=persona_search,
        document_search=document_search,
        parameter_search=parameter_search,
        problem_statement_search=problem_statement_search,
        image_search=image_search,
        video_search=video_search,
        question_search=question_search,
        option_search=option_search,
        persona_show_selected=persona_show_selected,
        document_show_selected=document_show_selected,
        parameter_show_selected=parameter_show_selected,
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, SCENARIO_RESOURCES)

    return build_scenario_get_result(
        common=common,
        scenario=scenario,
        scores=scores,
        perms=perms,
        group_id=effective_group_id,
    )
