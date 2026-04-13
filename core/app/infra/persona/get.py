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
from app.infra.persona.types import GetPersonaApiResponse, SectionFilter

SECTIONS = [
    "names", "descriptions", "colors", "icons", "instructions",
    "departments", "examples", "parameter_fields", "voices",
]


def _sf(filters: dict[str, SectionFilter | None], section: str, attr: str, default=None):
    """Get a SectionFilter attribute for a section, with default."""
    sf = filters.get(section)
    if sf is None:
        return default
    return getattr(sf, attr, default)


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
    # Per-section filters (nested SectionFilter objects)
    filters: dict[str, SectionFilter | None] | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> GetPersonaApiResponse:
    """Resolve the canonical persona artifact bundle for any surface."""
    f = filters or {}
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
        names_search=_sf(f, "names", "search"),
        descriptions_search=_sf(f, "descriptions", "search"),
        colors_search=_sf(f, "colors", "search"),
        icons_search=_sf(f, "icons", "search"),
        instructions_search=_sf(f, "instructions", "search"),
        departments_search=_sf(f, "departments", "search"),
        examples_search=_sf(f, "examples", "search"),
        parameter_fields_search=_sf(f, "parameter_fields", "search"),
        voices_search=_sf(f, "voices", "search"),
        names_limit=_sf(f, "names", "limit"),
        descriptions_limit=_sf(f, "descriptions", "limit"),
        colors_limit=_sf(f, "colors", "limit"),
        icons_limit=_sf(f, "icons", "limit"),
        instructions_limit=_sf(f, "instructions", "limit"),
        departments_limit=_sf(f, "departments", "limit"),
        examples_limit=_sf(f, "examples", "limit"),
        parameter_fields_limit=_sf(f, "parameter_fields", "limit"),
        voices_limit=_sf(f, "voices", "limit"),
        names_selected_only=_sf(f, "names", "selected"),
        descriptions_selected_only=_sf(f, "descriptions", "selected"),
        colors_selected_only=_sf(f, "colors", "selected"),
        icons_selected_only=_sf(f, "icons", "selected"),
        instructions_selected_only=_sf(f, "instructions", "selected"),
        departments_selected_only=_sf(f, "departments", "selected"),
        examples_selected_only=_sf(f, "examples", "selected"),
        parameter_fields_selected_only=_sf(f, "parameter_fields", "selected"),
        voices_selected_only=_sf(f, "voices", "selected"),
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, PERSONA_RESOURCES)

    include = {s: _sf(f, s, "include") is not False for s in SECTIONS}
    selected_only = {s: _sf(f, s, "selected") or False for s in SECTIONS}
    suggested_only = {s: _sf(f, s, "suggested") or False for s in SECTIONS}

    return build_persona_get_result(
        common=common,
        persona=persona,
        scores=scores,
        perms=perms,
        group_id=effective_group_id,
        include=include,
        selected_only=selected_only,
        suggested_only=suggested_only,
    )
