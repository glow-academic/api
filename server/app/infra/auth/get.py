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
from app.infra.auth.permissions_context import (
    resolve_auth_permissions_context,
)
from app.infra.common_context import resolve_common_context
from app.infra.helpers import dedupe_by_id
from app.infra.tool_graph import score_tools
from app.infra.auth.types import (
    AuthDescriptionSection,
    AuthFlagConfig,
    AuthFlagSection,
    AuthItemResource,
    AuthItemSection,
    AuthNameSection,
    AuthProtocolSection,
    AuthSlugSection,
    GetAuthApiResponse,
)


def derive_flag_key_and_label(name: str | None) -> tuple[str, str]:
    """Derive key and label from flag name like 'auth_active' -> ('active', 'Active')."""
    if not name:
        return ("unknown", "Unknown")
    key = name.replace("auth_", "")
    label = key.replace("_", " ").title()
    return (key, label)


async def get_auth_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    auth_id: UUID | None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    bypass_cache: bool = False,
) -> GetAuthApiResponse:
    """Resolve the canonical auth response for any surface."""
    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        draft_id=draft_id,
        artifact_type="auth",
        bypass_cache=bypass_cache,
    )
    if common is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    group_id = group_id or common.profile.group_id
    profile = common.profile

    if auth_id is not None:
        async with pool.acquire() as conn:
            perms = await resolve_auth_permissions_context(conn, auth_id)
        if not perms.exists:
            raise HTTPException(status_code=404, detail=f"Auth {auth_id} not found")

    auth_ctx = await resolve_auth_context(
        pool,
        redis,
        auth_id=auth_id,
        group_id=group_id,
        draft_id=draft_id,
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, AUTH_RESOURCES)
    agent_ids: dict[str, UUID | None] = {
        resource: (
            scores.best[resource].agent_id if scores.best.get(resource) else None
        )
        for resource in AUTH_RESOURCES
    }
    tool_ids_map: dict[str, UUID | None] = {
        resource: (scores.best[resource].tool_id if scores.best.get(resource) else None)
        for resource in AUTH_RESOURCES
    }

    can_edit = compute_can_edit(user_role=profile.role)
    disabled_reason = compute_disabled_reason(user_role=profile.role)

    names_has_tools = scores.has_any.get("names", False)
    protocols_has_tools = scores.has_any.get("protocols", False)
    slugs_has_tools = scores.has_any.get("slugs", False)

    all_protocols = dedupe_by_id(
        auth_ctx.resources["protocols"].selected
        + auth_ctx.resources["protocols"].suggestions
    )
    all_slugs = dedupe_by_id(
        auth_ctx.resources["slugs"].selected + auth_ctx.resources["slugs"].suggestions
    )

    show_flags_map = {
        "names": compute_show_name(names_has_tools),
        "descriptions": compute_show_description(),
        "flags": compute_show_flag(),
        "protocols": compute_show_protocols(protocols_has_tools, len(all_protocols)),
        "slugs": compute_show_slugs(slugs_has_tools, len(all_slugs)),
        "items": True,
    }
    required_flags_map = {
        "names": compute_name_required(),
        "descriptions": compute_description_required(),
        "flags": compute_flag_required(),
        "protocols": compute_protocols_required(show_flags_map["protocols"]),
        "slugs": compute_slugs_required(show_flags_map["slugs"]),
        "items": False,
    }
    show_ai_generate_map = {
        resource: (agent_ids.get(resource) is not None) for resource in AUTH_RESOURCES
    }
    basic_show_ai_generate = any(
        show_ai_generate_map.get(resource, False) for resource in AUTH_BASIC_RESOURCES
    )

    all_flags = dedupe_by_id(
        auth_ctx.resources["flags"].selected + auth_ctx.resources["flags"].suggestions
    )
    auth_flags = [
        AuthFlagConfig(
            key=derive_flag_key_and_label(flag.name)[0],
            label=derive_flag_key_and_label(flag.name)[1],
            description=flag.description,
            icon_id=flag.icon,
            flag_option_id=flag.id,
            show=show_flags_map.get("flags", True),
            required=required_flags_map.get("flags", False),
            generated=flag.generated,
        )
        for flag in all_flags
        if flag.id
    ]
    current_flags = [
        AuthFlagConfig(
            key=derive_flag_key_and_label(flag.name)[0],
            label=derive_flag_key_and_label(flag.name)[1],
            description=flag.description,
            icon_id=flag.icon,
            flag_option_id=flag.id,
            show=show_flags_map.get("flags", True),
            required=required_flags_map.get("flags", False),
            generated=flag.generated,
        )
        for flag in auth_ctx.resources["flags"].selected
        if flag.id
    ]

    all_names = dedupe_by_id(
        auth_ctx.resources["names"].selected + auth_ctx.resources["names"].suggestions
    )
    all_descriptions = dedupe_by_id(
        auth_ctx.resources["descriptions"].selected
        + auth_ctx.resources["descriptions"].suggestions
    )

    suggestions_map = {
        "names": [item.id for item in auth_ctx.resources["names"].suggestions],
        "descriptions": [
            item.id for item in auth_ctx.resources["descriptions"].suggestions
        ],
        "protocols": [item.id for item in auth_ctx.resources["protocols"].suggestions],
        "slugs": [item.id for item in auth_ctx.resources["slugs"].suggestions],
        "items": [],
    }

    def _section(resource_key: str) -> dict:
        return {
            "show": show_flags_map.get(resource_key, False),
            "required": required_flags_map.get(resource_key, False),
            "suggestions": suggestions_map.get(resource_key, []),
            "show_ai_generate": show_ai_generate_map.get(resource_key, False),
            "tool_id": tool_ids_map.get(resource_key),
        }

    items_as_resources = [
        AuthItemResource(
            auth_item_id=item.id,
            name=item.name,
            description=item.description,
            position=item.position,
            active=True,
            value_masked=None,
            key_id=None,
            encrypted=item.encrypted,
            generated=item.generated,
        )
        for item in auth_ctx.resources["items"].selected
    ]

    return GetAuthApiResponse(
        actor_name=profile.name,
        auth_exists=auth_ctx.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        draft_version=auth_ctx.draft_version,
        group_id=group_id,
        basic_show_ai_generate=basic_show_ai_generate,
        names=AuthNameSection(
            resource=auth_ctx.resources["names"].selected[0]
            if auth_ctx.resources["names"].selected
            else None,
            resources=all_names,
            **_section("names"),
        ),
        descriptions=AuthDescriptionSection(
            resource=auth_ctx.resources["descriptions"].selected[0]
            if auth_ctx.resources["descriptions"].selected
            else None,
            resources=all_descriptions,
            **_section("descriptions"),
        ),
        flags=AuthFlagSection(
            current=current_flags or None,
            resources=auth_flags,
            **_section("flags"),
        ),
        protocols=AuthProtocolSection(
            current=auth_ctx.resources["protocols"].selected or None,
            resources=all_protocols,
            **_section("protocols"),
        ),
        slugs=AuthSlugSection(
            current=auth_ctx.resources["slugs"].selected or None,
            resources=all_slugs,
            **_section("slugs"),
        ),
        items=AuthItemSection(
            current=items_as_resources or None,
            resources=items_as_resources,
            **_section("items"),
        ),
    )
