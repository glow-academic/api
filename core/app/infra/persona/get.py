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
    id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    parameter_ids: list[UUID] | None = None,
    # Per-section search (text filter)
    names_search: str | None = None,
    descriptions_search: str | None = None,
    colors_search: str | None = None,
    icons_search: str | None = None,
    instructions_search: str | None = None,
    departments_search: str | None = None,
    examples_search: str | None = None,
    parameter_fields_search: str | None = None,
    voices_search: str | None = None,
    # Per-section limit
    names_limit: int | None = None,
    descriptions_limit: int | None = None,
    colors_limit: int | None = None,
    icons_limit: int | None = None,
    instructions_limit: int | None = None,
    departments_limit: int | None = None,
    examples_limit: int | None = None,
    parameter_fields_limit: int | None = None,
    voices_limit: int | None = None,
    # Per-section selected_only
    names_selected_only: bool | None = None,
    descriptions_selected_only: bool | None = None,
    colors_selected_only: bool | None = None,
    icons_selected_only: bool | None = None,
    instructions_selected_only: bool | None = None,
    departments_selected_only: bool | None = None,
    examples_selected_only: bool | None = None,
    parameter_fields_selected_only: bool | None = None,
    voices_selected_only: bool | None = None,
    # Per-section include
    names_include: bool | None = None,
    descriptions_include: bool | None = None,
    colors_include: bool | None = None,
    icons_include: bool | None = None,
    instructions_include: bool | None = None,
    departments_include: bool | None = None,
    examples_include: bool | None = None,
    parameter_fields_include: bool | None = None,
    voices_include: bool | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> GetPersonaApiResponse:
    """Resolve the canonical persona artifact bundle for any surface."""
    persona_id = id  # alias: tools send 'id', internal code uses 'persona_id'
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
            common.profile.role_level,
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
        names_search=names_search,
        descriptions_search=descriptions_search,
        colors_search=colors_search,
        icons_search=icons_search,
        instructions_search=instructions_search,
        departments_search=departments_search,
        examples_search=examples_search,
        parameter_fields_search=parameter_fields_search,
        voices_search=voices_search,
        names_limit=names_limit,
        descriptions_limit=descriptions_limit,
        colors_limit=colors_limit,
        icons_limit=icons_limit,
        instructions_limit=instructions_limit,
        departments_limit=departments_limit,
        examples_limit=examples_limit,
        parameter_fields_limit=parameter_fields_limit,
        voices_limit=voices_limit,
        names_selected_only=names_selected_only,
        descriptions_selected_only=descriptions_selected_only,
        colors_selected_only=colors_selected_only,
        icons_selected_only=icons_selected_only,
        instructions_selected_only=instructions_selected_only,
        departments_selected_only=departments_selected_only,
        examples_selected_only=examples_selected_only,
        parameter_fields_selected_only=parameter_fields_selected_only,
        voices_selected_only=voices_selected_only,
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, PERSONA_RESOURCES)

    include = {
        "names": names_include is not False,
        "descriptions": descriptions_include is not False,
        "colors": colors_include is not False,
        "icons": icons_include is not False,
        "instructions": instructions_include is not False,
        "departments": departments_include is not False,
        "examples": examples_include is not False,
        "parameter_fields": parameter_fields_include is not False,
        "voices": voices_include is not False,
    }

    return build_persona_get_result(
        common=common,
        persona=persona,
        scores=scores,
        perms=perms,
        group_id=effective_group_id,
        include=include,
    )
