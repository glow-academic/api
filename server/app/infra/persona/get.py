"""Canonical shared persona GET operation."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.persona.context import resolve_persona_context
from app.infra.persona.permissions import PERSONA_RESOURCES, has_access
from app.infra.persona.permissions_context import resolve_persona_permissions_context
from app.infra.persona.sections import build_persona_get_result
from app.infra.tool_graph import score_tools
from app.infra.persona.types import GetPersonaApiResponse


async def get_persona_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    persona_id: UUID | None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    parameter_ids: list[UUID] | None = None,
    color_search: str | None = None,
    icon_search: str | None = None,
    descriptions_search: str | None = None,
    instructions_search: str | None = None,
    color_show_selected: bool | None = None,
    icon_show_selected: bool | None = None,
    bypass_cache: bool = False,
) -> GetPersonaApiResponse:
    """Resolve the canonical persona artifact bundle for any surface."""
    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        draft_id=draft_id,
        artifact_type="persona",
        bypass_cache=bypass_cache,
    )
    if common is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    effective_group_id = group_id or common.profile.group_id

    perms = None
    if persona_id is not None:
        perms = await resolve_persona_permissions_context(pool, persona_id)
        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Persona {persona_id} not found",
            )
        if not has_access(
            common.profile.role,
            common.profile.department_ids,
            perms.department_ids,
        ):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this persona.",
            )

    persona = await resolve_persona_context(
        pool,
        redis,
        persona_id=persona_id,
        group_id=effective_group_id,
        draft_id=draft_id,
        user_department_ids=common.profile.department_ids,
        parameter_ids=parameter_ids,
        color_search=color_search,
        icon_search=icon_search,
        descriptions_search=descriptions_search,
        instructions_search=instructions_search,
        color_show_selected=color_show_selected,
        icon_show_selected=icon_show_selected,
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, PERSONA_RESOURCES)

    return build_persona_get_result(
        common=common,
        persona=persona,
        scores=scores,
        perms=perms,
        group_id=effective_group_id,
    )
