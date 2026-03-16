"""Canonical shared cohort GET operation."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.cohort.context import resolve_cohort_context
from app.infra.cohort.permissions import COHORT_RESOURCES, has_access
from app.infra.cohort.permissions_context import resolve_cohort_permissions_context
from app.infra.cohort.sections import build_cohort_get_result
from app.infra.common_context import resolve_common_context
from app.infra.tool_graph import score_tools
from app.infra.cohort.types import GetCohortApiResponse


async def get_cohort_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    cohort_id: UUID | None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    descriptions_search: str | None = None,
    simulation_search: str | None = None,
    simulation_show_selected: bool | None = None,
    profile_search: str | None = None,
    profile_show_selected: bool | None = None,
    bypass_cache: bool = False,
) -> GetCohortApiResponse:
    """Resolve the canonical cohort artifact bundle for any surface."""
    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        draft_id=draft_id,
        artifact_type="cohort",
        bypass_cache=bypass_cache,
    )
    if common is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    effective_group_id = group_id or common.profile.group_id
    perms = None
    if cohort_id is not None:
        async with pool.acquire() as conn:
            perms = await resolve_cohort_permissions_context(conn, cohort_id)
        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Cohort {cohort_id} not found",
            )
        if not has_access(
            common.profile.role,
            common.profile.department_ids,
            perms.department_ids,
        ):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this cohort. It may be restricted to other departments.",
            )

    cohort = await resolve_cohort_context(
        pool,
        redis,
        cohort_id=cohort_id,
        group_id=effective_group_id,
        draft_id=draft_id,
        user_department_ids=common.profile.department_ids,
        descriptions_search=descriptions_search,
        simulation_search=simulation_search,
        simulation_show_selected=simulation_show_selected,
        profile_search=profile_search,
        profile_show_selected=profile_show_selected,
        bypass_cache=bypass_cache,
    )
    scores = score_tools(common.tool_graph, COHORT_RESOURCES)

    return build_cohort_get_result(
        common=common,
        cohort=cohort,
        scores=scores,
        perms=perms,
        cohort_id=cohort_id,
        group_id=effective_group_id,
    )
