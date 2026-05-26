"""Canonical shared cohort GET operation."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.cohort.context import resolve_cohort_context
from app.infra.cohort.permissions import (
    compute_can_draft,
    compute_can_edit,
    compute_disabled_reason,
    has_access,
)
from app.infra.cohort.permissions_context import resolve_cohort_permissions_context
from app.infra.cohort.types import (
    GetCohortApiResponse,
)
from app.infra.common_context import resolve_common_context
from app.infra.group.resolve import resolve_group_impl
from app.infra.server_timing import timed


def _sf(filters: dict[str, Any | None], section: str, attr: str, default=None):
    """Get a section filter attribute with a default."""
    sf = filters.get(section)
    if sf is None:
        return default
    if isinstance(sf, dict):
        return sf.get(attr, default)
    return getattr(sf, attr, default)


def _legacy_section_filter(
    *,
    search: str | None = None,
    limit: int | None = None,
    selected: bool | None = None,
    suggested: bool | None = None,
    include: bool | None = True,
    parameter_ids: list[str] | None = None,
) -> SimpleNamespace:
    """Build a light-weight SectionFilter-compatible object for legacy inputs."""
    return SimpleNamespace(
        search=search,
        limit=limit,
        selected=selected,
        suggested=suggested,
        include=include,
        parameter_ids=parameter_ids,
    )


def _section_included(filters: dict[str, Any | None], section: str) -> bool:
    return _sf(filters, section, "include", True) is not False


def _apply_section_filters(
    items: list | None,
    *,
    filters: dict[str, Any | None],
    section: str,
) -> list | None:
    if items is None:
        return None
    if not _section_included(filters, section):
        return None
    if _sf(filters, section, "selected"):
        items = [item for item in items if getattr(item, "selected", False)]
    if _sf(filters, section, "suggested"):
        items = [item for item in items if getattr(item, "suggested", False)]
    return items


def _with_flags(
    *,
    items: list,
    selected_ids: set[UUID],
    suggested_ids: set[UUID],
    pending_ids: set[UUID],
    model_cls,
    transform,
    section: str,
    filters: dict[str, Any | None],
) -> list | None:
    if not _section_included(filters, section):
        return None

    result: list = []
    seen: set[UUID] = set()
    for item in items:
        item_id = getattr(item, "id", None)
        if item_id is None or item_id in seen:
            continue
        seen.add(item_id)
        payload = transform(item)
        payload["selected"] = item_id in selected_ids
        payload["suggested"] = item_id in suggested_ids
        payload["pending"] = item_id in pending_ids
        result.append(model_cls.model_validate(payload))
    return _apply_section_filters(result, filters=filters, section=section)


async def get_cohort_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    cohort_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    filters: dict[str, Any | None] | None = None,
    descriptions_search: str | None = None,
    simulation_search: str | None = None,
    simulation_show_selected: bool | None = None,
    profile_search: str | None = None,
    profile_show_selected: bool | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> GetCohortApiResponse:
    """Resolve the canonical cohort artifact bundle for any surface."""
    effective_filters: dict[str, Any | None] = dict(filters or {})
    fallback_filters = {
        "names": _legacy_section_filter(),
        "descriptions": _legacy_section_filter(search=descriptions_search),
        "flags": _legacy_section_filter(),
        "departments": _legacy_section_filter(),
        "simulations": _legacy_section_filter(
            search=simulation_search,
            selected=simulation_show_selected,
        ),
        "simulation_positions": _legacy_section_filter(),
        "simulation_availability": _legacy_section_filter(),
        "profiles": _legacy_section_filter(
            search=profile_search,
            selected=profile_show_selected,
        ),
        "profile_personas": _legacy_section_filter(),
        "personas": _legacy_section_filter(),
    }
    for section, value in fallback_filters.items():
        effective_filters.setdefault(section, value)

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
                artifact_type="cohort",
                profile_id=profile_id,
                session_id=session_id,
                include_history=False,
            )
            group_id = _gr.group_id
    effective_group_id = group_id
    perms = None
    if cohort_id is not None:
        with timed("permissions"):
            async with pool.acquire() as conn:
                perms = await resolve_cohort_permissions_context(conn, cohort_id)
        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Cohort {cohort_id} not found",
            )
        if not has_access(
            common.profile.role_level,
            common.profile.department_ids,
            perms.department_ids,
        ):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this cohort. It may be restricted to other departments.",
            )

    with timed("cohort_ctx"):
        cohort = await resolve_cohort_context(
            pool,
            redis,
            cohort_id=cohort_id,
            group_id=effective_group_id,
            draft_id=draft_id,
            user_department_ids=common.profile.department_ids,
            filters=effective_filters,
            bypass_cache=bypass_cache,
        )

    profile = common.profile
    cohort_department_ids = list(perms.department_ids) if perms else [
        department.id
        for department in cohort.resources["departments"].selected
        if getattr(department, "id", None)
    ]

    can_edit = compute_can_edit(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
        cohort_department_ids=cohort_department_ids,
        user_department_ids=profile.department_ids,
    )
    disabled_reason = compute_disabled_reason(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
        cohort_department_ids=cohort_department_ids,
        user_department_ids=profile.department_ids,
    )

    can_draft = compute_can_draft(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
    )

    pending_ids = set(cohort.entries.get("pending_ids", set()) or set())

    selected_names = {item.id for item in cohort.resources["names"].selected if item.id}
    suggested_names = {
        item.id for item in cohort.resources["names"].suggestions if item.id
    }
    selected_descriptions = {
        item.id for item in cohort.resources["descriptions"].selected if item.id
    }
    suggested_descriptions = {
        item.id for item in cohort.resources["descriptions"].suggestions if item.id
    }
    selected_flags = {item.id for item in cohort.resources["flags"].selected if item.id}
    suggested_flags = {
        item.id for item in cohort.resources["flags"].suggestions if item.id
    }
    selected_departments = {
        item.id for item in cohort.resources["departments"].selected if item.id
    }
    suggested_departments = {
        item.id for item in cohort.resources["departments"].suggestions if item.id
    }
    selected_simulations = {
        item.id for item in cohort.resources["simulations"].selected if item.id
    }
    suggested_simulations = {
        item.id for item in cohort.resources["simulations"].suggestions if item.id
    }
    selected_simulation_positions = {
        item.id for item in cohort.resources["simulation_positions"].selected if item.id
    }
    suggested_simulation_positions = {
        item.id for item in cohort.resources["simulation_positions"].suggestions if item.id
    }
    selected_simulation_availability = {
        item.id for item in cohort.resources["simulation_availability"].selected if item.id
    }
    suggested_simulation_availability = {
        item.id for item in cohort.resources["simulation_availability"].suggestions
        if item.id
    }
    selected_profiles = {
        item.id for item in cohort.resources["profiles"].selected if item.id
    }
    suggested_profiles = {
        item.id for item in cohort.resources["profiles"].suggestions if item.id
    }
    selected_profile_personas = {
        item.id for item in cohort.resources["profile_personas"].selected if item.id
    }

    from app.infra.cohort.types import (
        CohortDepartment,
        CohortDescriptionResource,
        CohortFlagResource,
        CohortNameResource,
        CohortPersonaResource,
        CohortProfile,
        CohortProfilePersona,
        CohortSimulation,
        CohortSimulationAvailability,
        CohortSimulationPosition,
    )
    from app.infra.helpers import sorted_dedupe_by_id

    names = _with_flags(
        items=sorted_dedupe_by_id(cohort.resources["names"].suggestions + cohort.resources["names"].selected),
        selected_ids=selected_names,
        suggested_ids=suggested_names,
        pending_ids=pending_ids,
        model_cls=CohortNameResource,
        transform=lambda item: {
            "id": item.id,
            "name": item.name,
            "generated": item.generated,
        },
        section="names",
        filters=effective_filters,
    )
    descriptions = _with_flags(
        items=sorted_dedupe_by_id(
            cohort.resources["descriptions"].suggestions
            + cohort.resources["descriptions"].selected
        ),
        selected_ids=selected_descriptions,
        suggested_ids=suggested_descriptions,
        pending_ids=pending_ids,
        model_cls=CohortDescriptionResource,
        transform=lambda item: {
            "id": item.id,
            "description": item.description,
            "generated": item.generated,
        },
        section="descriptions",
        filters=effective_filters,
    )
    flags = _with_flags(
        items=sorted_dedupe_by_id(cohort.resources["flags"].suggestions + cohort.resources["flags"].selected),
        selected_ids=selected_flags,
        suggested_ids=suggested_flags,
        pending_ids=pending_ids,
        model_cls=CohortFlagResource,
        transform=lambda item: {
            "id": item.id,
            "name": getattr(item, "name", None),
            "type": getattr(item, "type", None),
            "value": getattr(item, "value", None),
            "description": item.description,
            "icon_id": item.icon_id,
            "icon": getattr(item, "icon", None),
            "generated": item.generated,
        },
        section="flags",
        filters=effective_filters,
    )
    departments = _with_flags(
        items=sorted_dedupe_by_id(
            cohort.resources["departments"].suggestions
            + cohort.resources["departments"].selected
        ),
        selected_ids=selected_departments,
        suggested_ids=suggested_departments,
        pending_ids=pending_ids,
        model_cls=CohortDepartment,
        transform=lambda item: {
            "department_id": item.id,
            "name": item.name,
            "description": item.description,
            "generated": item.generated,
        },
        section="departments",
        filters=effective_filters,
    )
    simulations = _with_flags(
        items=sorted_dedupe_by_id(
            cohort.resources["simulations"].suggestions
            + cohort.resources["simulations"].selected
        ),
        selected_ids=selected_simulations,
        suggested_ids=suggested_simulations,
        pending_ids=pending_ids,
        model_cls=CohortSimulation,
        transform=lambda item: {
            "simulation_id": item.id,
            "name": item.name,
            "description": item.description,
            "generated": item.generated,
        },
        section="simulations",
        filters=effective_filters,
    )
    simulation_positions = _with_flags(
        items=sorted_dedupe_by_id(
            cohort.resources["simulation_positions"].suggestions
            + cohort.resources["simulation_positions"].selected
        ),
        selected_ids=selected_simulation_positions,
        suggested_ids=suggested_simulation_positions,
        pending_ids=pending_ids,
        model_cls=CohortSimulationPosition,
        transform=lambda item: {
            "id": item.id,
            "simulation_id": item.simulation_id,
            "value": item.value,
            "generated": item.generated,
            "mcp": item.mcp,
        },
        section="simulation_positions",
        filters=effective_filters,
    )
    simulation_availability = _with_flags(
        items=sorted_dedupe_by_id(
            cohort.resources["simulation_availability"].suggestions
            + cohort.resources["simulation_availability"].selected
        ),
        selected_ids=selected_simulation_availability,
        suggested_ids=suggested_simulation_availability,
        pending_ids=pending_ids,
        model_cls=CohortSimulationAvailability,
        transform=lambda item: {
            "id": item.id,
            "simulation_id": item.simulation_id,
            "time": item.time,
            "type": item.type,
            "generated": item.generated,
            "mcp": item.mcp,
        },
        section="simulation_availability",
        filters=effective_filters,
    )
    profiles = _with_flags(
        items=sorted_dedupe_by_id(
            cohort.resources["profiles"].suggestions + cohort.resources["profiles"].selected
        ),
        selected_ids=selected_profiles,
        suggested_ids=suggested_profiles,
        pending_ids=pending_ids,
        model_cls=CohortProfile,
        transform=lambda item: {
            "profile_id": item.id,
            "name": item.name,
            "description": item.description,
            "generated": item.generated,
            "mcp": item.mcp,
        },
        section="profiles",
        filters=effective_filters,
    )
    profile_personas = _with_flags(
        items=sorted_dedupe_by_id(
            cohort.resources["profile_personas"].suggestions
            + cohort.resources["profile_personas"].selected
        ),
        selected_ids=selected_profile_personas,
        suggested_ids=set(),
        pending_ids=pending_ids,
        model_cls=CohortProfilePersona,
        transform=lambda item: {
            "id": item.id,
            "profile_id": item.profile_id,
            "persona_id": item.persona_id,
            "generated": item.generated,
            "mcp": item.mcp,
        },
        section="profile_personas",
        filters=effective_filters,
    )
    personas = _with_flags(
        items=sorted_dedupe_by_id(cohort.resources["personas"].suggestions),
        selected_ids=set(),
        suggested_ids={item.id for item in cohort.resources["personas"].suggestions if item.id},
        pending_ids=pending_ids,
        model_cls=CohortPersonaResource,
        transform=lambda item: item.model_dump(),
        section="personas",
        filters=effective_filters,
    )

    with timed("build"):
        return GetCohortApiResponse(
            actor_name=profile.name,
            cohort_exists=cohort.artifact_id is not None,
            can_edit=can_edit,
            disabled_reason=disabled_reason,
            group_id=effective_group_id,
            show_ai_generate=can_draft,
            names=names,
            descriptions=descriptions,
            flags=flags,
            departments=departments,
            simulations=simulations,
            simulation_positions=simulation_positions,
            simulation_availability=simulation_availability,
            profiles=profiles,
            profile_personas=profile_personas,
            personas=personas,
            pending_ids=sorted(pending_ids, key=str),
            basic_show_ai_generate=can_draft,
            simulations_step_show_ai_generate=can_draft,
            profiles_step_show_ai_generate=can_draft,
        )
