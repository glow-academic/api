"""Canonical shared auth GET operation."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.auth.context import resolve_auth_context
from app.infra.auth.permissions import (
    AUTH_BASIC_RESOURCES,
    AUTH_RESOURCES,
    compute_can_edit,
    compute_description_required,
    compute_disabled_reason,
    compute_flag_required,
    compute_name_required,
    compute_protocols_required,
    compute_show_description,
    compute_show_flag,
    compute_show_name,
    compute_show_protocols,
    compute_show_slugs,
    compute_slugs_required,
)
from app.infra.auth.permissions_context import resolve_auth_permissions_context
from app.infra.auth.types import (
    AuthDepartmentResource,
    AuthDescriptionResource,
    AuthFlagResource,
    AuthItemResource,
    AuthNameResource,
    AuthProtocolResource,
    AuthSlugResource,
    GetAuthApiResponse,
    SectionFilter,
)
from app.infra.common_context import resolve_common_context
from app.infra.group.resolve import resolve_group_impl
from app.infra.helpers import sorted_dedupe_by_id
from app.infra.tool_graph import score_tools

SECTIONS = ["names", "descriptions", "flags", "departments", "protocols", "slugs", "items"]


def derive_flag_key_and_label(name: str | None) -> tuple[str, str]:
    """Derive key and label from flag name like 'auth_active'."""
    if not name:
        return ("unknown", "Unknown")
    key = name.replace("auth_", "")
    return (key, key.replace("_", " ").title())


def _sf(filters: dict[str, SectionFilter | None], section: str, attr: str, default=None):
    sf = filters.get(section)
    if sf is None:
        return default
    return getattr(sf, attr, default)


def _filter_resources(items: list, *, selected_only: bool, suggested_only: bool) -> list:
    output = items
    if selected_only:
        output = [item for item in output if getattr(item, "selected", False)]
    if suggested_only:
        output = [item for item in output if getattr(item, "suggested", False)]
    return output


async def get_auth_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    id: UUID | None = None,
    auth_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    filters: dict[str, SectionFilter | None] | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> GetAuthApiResponse:
    """Resolve the canonical auth response for any surface."""
    f = filters or {}
    resolved_auth_id = id or auth_id

    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        bypass_cache=bypass_cache,
    )
    if common is None:
        raise HTTPException(status_code=401, detail="Profile not found. Please sign in again.")

    if group_id is None:
        _gr = await resolve_group_impl(
            pool, redis,
            artifact_type="auth",
            profile_id=profile_id,
            session_id=session_id,
            include_history=False,
        )
        group_id = _gr.group_id
    effective_group_id = group_id
    profile = common.profile

    if resolved_auth_id is not None:
        async with pool.acquire() as conn:
            perms = await resolve_auth_permissions_context(conn, resolved_auth_id)
        if not perms.exists:
            raise HTTPException(status_code=404, detail=f"Auth {resolved_auth_id} not found")

    auth_ctx = await resolve_auth_context(
        pool,
        redis,
        auth_id=resolved_auth_id,
        group_id=effective_group_id,
        draft_id=draft_id,
        names_search=_sf(f, "names", "search"),
        descriptions_search=_sf(f, "descriptions", "search"),
        departments_search=_sf(f, "departments", "search"),
        protocols_search=_sf(f, "protocols", "search"),
        slugs_search=_sf(f, "slugs", "search"),
        items_search=_sf(f, "items", "search"),
        names_limit=_sf(f, "names", "limit"),
        descriptions_limit=_sf(f, "descriptions", "limit"),
        departments_limit=_sf(f, "departments", "limit"),
        protocols_limit=_sf(f, "protocols", "limit"),
        slugs_limit=_sf(f, "slugs", "limit"),
        items_limit=_sf(f, "items", "limit"),
        names_selected_only=_sf(f, "names", "selected"),
        descriptions_selected_only=_sf(f, "descriptions", "selected"),
        departments_selected_only=_sf(f, "departments", "selected"),
        protocols_selected_only=_sf(f, "protocols", "selected"),
        slugs_selected_only=_sf(f, "slugs", "selected"),
        items_selected_only=_sf(f, "items", "selected"),
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, AUTH_RESOURCES)
    can_edit = compute_can_edit(role_level=profile.role_level, role_permissions=profile.role_permissions)
    disabled_reason = compute_disabled_reason(role_permissions=profile.role_permissions)

    include = {section: _sf(f, section, "include") is not False for section in SECTIONS}
    selected_only = {section: bool(_sf(f, section, "selected")) for section in SECTIONS}
    suggested_only = {section: bool(_sf(f, section, "suggested")) for section in SECTIONS}
    pending_ids = set(auth_ctx.entries.get("pending_ids", set()))

    show_flags_map = {
        "names": compute_show_name(scores.has_any.get("names", False)),
        "descriptions": compute_show_description(),
        "flags": compute_show_flag(),
        "protocols": compute_show_protocols(scores.has_any.get("protocols", False), len(auth_ctx.resources["protocols"].selected) + len(auth_ctx.resources["protocols"].suggestions)),
        "slugs": compute_show_slugs(scores.has_any.get("slugs", False), len(auth_ctx.resources["slugs"].selected) + len(auth_ctx.resources["slugs"].suggestions)),
    }
    required_flags_map = {
        "names": compute_name_required(),
        "descriptions": compute_description_required(),
        "flags": compute_flag_required(),
        "protocols": compute_protocols_required(show_flags_map["protocols"]),
        "slugs": compute_slugs_required(show_flags_map["slugs"]),
    }

    names = None
    if include["names"]:
        selected_ids = {item.id for item in auth_ctx.resources["names"].selected if item.id}
        suggested_ids = {item.id for item in auth_ctx.resources["names"].suggestions if item.id}
        merged = sorted_dedupe_by_id(auth_ctx.resources["names"].suggestions + auth_ctx.resources["names"].selected)
        names = _filter_resources(
            [
                AuthNameResource(
                    id=item.id,
                    name=item.name,
                    generated=item.generated,
                    selected=item.id in selected_ids if item.id else False,
                    suggested=item.id in suggested_ids if item.id else False,
                    pending=item.id in pending_ids if item.id else False,
                )
                for item in merged
            ],
            selected_only=selected_only["names"],
            suggested_only=suggested_only["names"],
        )

    descriptions = None
    if include["descriptions"]:
        selected_ids = {item.id for item in auth_ctx.resources["descriptions"].selected if item.id}
        suggested_ids = {item.id for item in auth_ctx.resources["descriptions"].suggestions if item.id}
        merged = sorted_dedupe_by_id(auth_ctx.resources["descriptions"].suggestions + auth_ctx.resources["descriptions"].selected)
        descriptions = _filter_resources(
            [
                AuthDescriptionResource(
                    id=item.id,
                    description=item.description,
                    generated=item.generated,
                    selected=item.id in selected_ids if item.id else False,
                    suggested=item.id in suggested_ids if item.id else False,
                    pending=item.id in pending_ids if item.id else False,
                )
                for item in merged
            ],
            selected_only=selected_only["descriptions"],
            suggested_only=suggested_only["descriptions"],
        )

    flags = None
    if include["flags"]:
        selected_ids = {item.id for item in auth_ctx.resources["flags"].selected if item.id}
        suggested_ids = {item.id for item in auth_ctx.resources["flags"].suggestions if item.id}
        merged = sorted_dedupe_by_id(auth_ctx.resources["flags"].suggestions + auth_ctx.resources["flags"].selected)
        flags = _filter_resources(
            [
                AuthFlagResource(
                    id=item.id,
                    name=getattr(item, "name", None),
                    type=getattr(item, "type", None),
                    value=getattr(item, "value", None),
                    description=item.description,
                    icon_id=getattr(item, "icon_id", None),
                    icon=getattr(item, "icon", None),
                    generated=item.generated,
                    selected=item.id in selected_ids if item.id else False,
                    suggested=item.id in suggested_ids if item.id else False,
                    pending=item.id in pending_ids if item.id else False,
                )
                for item in merged
                if item.id
            ],
            selected_only=selected_only["flags"],
            suggested_only=suggested_only["flags"],
        )

    departments = None
    if include["departments"]:
        selected_ids = {item.id for item in auth_ctx.resources["departments"].selected if item.id}
        suggested_ids = {item.id for item in auth_ctx.resources["departments"].suggestions if item.id}
        merged = sorted_dedupe_by_id(auth_ctx.resources["departments"].suggestions + auth_ctx.resources["departments"].selected)
        departments = _filter_resources(
            [
                AuthDepartmentResource(
                    department_id=item.id,
                    name=item.name,
                    description=item.description,
                    generated=item.generated,
                    selected=item.id in selected_ids if item.id else False,
                    suggested=item.id in suggested_ids if item.id else False,
                    pending=item.id in pending_ids if item.id else False,
                )
                for item in merged
            ],
            selected_only=selected_only["departments"],
            suggested_only=suggested_only["departments"],
        )

    protocols = None
    if include["protocols"]:
        selected_ids = {item.id for item in auth_ctx.resources["protocols"].selected if item.id}
        suggested_ids = {item.id for item in auth_ctx.resources["protocols"].suggestions if item.id}
        merged = sorted_dedupe_by_id(auth_ctx.resources["protocols"].suggestions + auth_ctx.resources["protocols"].selected)
        protocols = _filter_resources(
            [
                AuthProtocolResource(
                    id=item.id,
                    value=item.value,
                    generated=item.generated,
                    selected=item.id in selected_ids if item.id else False,
                    suggested=item.id in suggested_ids if item.id else False,
                    pending=item.id in pending_ids if item.id else False,
                )
                for item in merged
            ],
            selected_only=selected_only["protocols"],
            suggested_only=suggested_only["protocols"],
        )

    slugs = None
    if include["slugs"]:
        selected_ids = {item.id for item in auth_ctx.resources["slugs"].selected if item.id}
        suggested_ids = {item.id for item in auth_ctx.resources["slugs"].suggestions if item.id}
        merged = sorted_dedupe_by_id(auth_ctx.resources["slugs"].suggestions + auth_ctx.resources["slugs"].selected)
        slugs = _filter_resources(
            [
                AuthSlugResource(
                    id=item.id,
                    value=item.value,
                    generated=item.generated,
                    selected=item.id in selected_ids if item.id else False,
                    suggested=item.id in suggested_ids if item.id else False,
                    pending=item.id in pending_ids if item.id else False,
                )
                for item in merged
            ],
            selected_only=selected_only["slugs"],
            suggested_only=suggested_only["slugs"],
        )

    items = None
    if include["items"]:
        selected_ids = {item.id for item in auth_ctx.resources["items"].selected if item.id}
        suggested_ids = {item.id for item in auth_ctx.resources["items"].suggestions if item.id}
        merged = sorted_dedupe_by_id(auth_ctx.resources["items"].suggestions + auth_ctx.resources["items"].selected)
        items = _filter_resources(
            [
                AuthItemResource(
                    id=item.id,
                    name=item.name,
                    description=item.description,
                    position=item.position,
                    encrypted=item.encrypted,
                    generated=item.generated,
                    selected=item.id in selected_ids if item.id else False,
                    suggested=item.id in suggested_ids if item.id else False,
                    pending=item.id in pending_ids if item.id else False,
                )
                for item in merged
            ],
            selected_only=selected_only["items"],
            suggested_only=suggested_only["items"],
        )

    return GetAuthApiResponse(
        actor_name=profile.name,
        auth_exists=auth_ctx.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        group_id=effective_group_id,
        show_ai_generate=any(scores.has_any.get(resource, False) for resource in AUTH_RESOURCES),
        basic_show_ai_generate=any(scores.has_any.get(resource, False) for resource in AUTH_BASIC_RESOURCES),
        pending_ids=list(pending_ids),
        names=names,
        descriptions=descriptions,
        flags=flags,
        departments=departments,
        protocols=protocols,
        slugs=slugs,
        items=items,
    )
