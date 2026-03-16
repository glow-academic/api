"""Canonical shared profile get operation.

Uses composable infra layers:
  1. resolve_common_context — profile + tool graph + runs
  2. resolve_profile_permissions_context — fail-fast 404/403
  3. resolve_profile_context — artifact + draft → merged + hydrated resources
  4. score_tools — tool graph + artifact resources → per-resource tool picks
  5. Pure Python — permissions, show/required flags, role_options, response assembly
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.helpers import dedupe_by_id
from app.infra.profile.context import resolve_profile_context
from app.infra.profile.permissions import (
    PROFILE_RESOURCES,
    compute_can_edit,
    compute_departments_required,
    compute_disabled_reason,
    compute_emails_required,
    compute_flag_required,
    compute_name_required,
    compute_request_limit_required,
    compute_role_options,
    compute_roles_required,
    compute_show_departments,
    compute_show_emails,
    compute_show_flag,
    compute_show_name,
    compute_show_request_limit,
    compute_show_roles,
    has_access,
)
from app.infra.profile.permissions_context import resolve_profile_permissions_context
from app.infra.tool_graph import score_tools
from app.infra.profile.types import (
    GetProfileApiResponse,
    ProfileDepartmentSection,
    ProfileEmailSection,
    ProfileFlagConfig,
    ProfileFlagSection,
    ProfileNameSection,
    ProfileRequestLimitSection,
    ProfileRoleSection,
)

# ---------------------------------------------------------------------------
# get_profile_impl — composable infra architecture
# ---------------------------------------------------------------------------


def derive_flag_key_and_label(name: str | None) -> tuple[str, str]:
    """Derive key and label from flag name like 'profile_active' -> ('active', 'Active')"""
    if not name:
        return ("unknown", "Unknown")
    key = name.replace("profile_", "")
    label = key.replace("_", " ").title()
    return (key, label)


def _serialize_model(item):
    if item is None:
        return None
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    return item


def _serialize_models(items: list) -> list:
    return [_serialize_model(item) for item in items]


async def get_profile_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    target_profile_id: UUID | None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    bypass_cache: bool = False,
) -> GetProfileApiResponse:
    """Profile GET using composable infra functions.

    Flow:
      1. resolve_common_context(profile_id) → profile, tool_graph, runs
      2. resolve_profile_permissions_context → access check (404, 403, fail fast)
      3. resolve_profile_context(target_profile_id, draft_id, ...) → hydrated resources
      4. score_tools(tool_graph, PROFILE_RESOURCES) → per-resource tool picks
      5. Pure Python: permissions, show/required/AI flags, role_options, response assembly
    """

    # ── Step 1: Common context (profile → tool_graph + runs) ──────────────

    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        draft_id=draft_id,
        artifact_type="profile",
        bypass_cache=bypass_cache,
    )

    if common is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    group_id = group_id or common.profile.group_id
    profile = common.profile

    # ── Step 2: Permissions check (fail fast before full hydration) ──────

    target_is_self = (
        target_profile_id is not None and profile_id == target_profile_id
    ) or target_profile_id is None

    perms = None
    if target_profile_id is not None:
        async with pool.acquire() as conn:
            perms = await resolve_profile_permissions_context(conn, target_profile_id)

        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Profile {target_profile_id} not found",
            )

        if not has_access(profile.role, profile.department_ids, perms.department_ids):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this profile. It may be restricted to other departments.",
            )

    # ── Step 3: Profile artifact context ─────────────────────────────────

    profile_ctx = await resolve_profile_context(
        pool,
        redis,
        profile_id=target_profile_id,
        group_id=group_id,
        draft_id=draft_id,
        user_department_ids=profile.department_ids,
        bypass_cache=bypass_cache,
    )

    # ── Step 4: Tool scoring ─────────────────────────────────────────────

    scores = score_tools(common.tool_graph, PROFILE_RESOURCES)

    agent_ids: dict[str, UUID | None] = {
        r: (scores.best[r].agent_id if scores.best.get(r) else None)
        for r in PROFILE_RESOURCES
    }

    tool_ids_map: dict[str, UUID | None] = {
        r: (scores.best[r].tool_id if scores.best.get(r) else None)
        for r in PROFILE_RESOURCES
    }

    # ── Step 5: Permissions ──────────────────────────────────────────────

    perms_department_ids = perms.department_ids if perms else []

    can_edit = compute_can_edit(
        user_role=profile.role,
        target_is_self=target_is_self,
        target_department_ids=perms_department_ids,
        user_department_ids=profile.department_ids,
    )

    disabled_reason = compute_disabled_reason(
        user_role=profile.role,
        target_is_self=target_is_self,
        target_department_ids=perms_department_ids,
    )

    # ── Step 6: Show / Required / AI flags ───────────────────────────────

    names_has_tools = scores.has_any.get("names", False)
    emails_has_tools = scores.has_any.get("emails", False)
    request_limits_has_tools = scores.has_any.get("request_limits", False)

    all_departments = dedupe_by_id(
        profile_ctx.resources["departments"].selected
        + profile_ctx.resources["departments"].suggestions
    )
    all_roles = dedupe_by_id(
        profile_ctx.resources["roles"].selected
        + profile_ctx.resources["roles"].suggestions
    )

    show_flags_map = {
        "names": compute_show_name(names_has_tools),
        "emails": compute_show_emails(emails_has_tools),
        "request_limits": compute_show_request_limit(request_limits_has_tools),
        "flags": compute_show_flag(),
        "departments": compute_show_departments(len(all_departments)),
        "roles": compute_show_roles(),
    }

    required_flags_map = {
        "names": compute_name_required(),
        "emails": compute_emails_required(),
        "request_limits": compute_request_limit_required(),
        "flags": compute_flag_required(),
        "departments": compute_departments_required(),
        "roles": compute_roles_required(),
    }

    def compute_show_ai_generate(resource: str) -> bool:
        return agent_ids.get(resource) is not None

    show_ai_generate_map = {r: compute_show_ai_generate(r) for r in PROFILE_RESOURCES}

    basic_show_ai_generate = any(
        [
            show_ai_generate_map.get("names", False),
            show_ai_generate_map.get("emails", False),
            show_ai_generate_map.get("flags", False),
            show_ai_generate_map.get("request_limits", False),
        ]
    )
    general_show_ai_generate = any(
        [
            show_ai_generate_map.get("names", False),
            show_ai_generate_map.get("emails", False),
            show_ai_generate_map.get("request_limits", False),
            show_ai_generate_map.get("flags", False),
            show_ai_generate_map.get("departments", False),
        ]
    )

    # ── Step 7: Role options (computed in Python from hierarchy) ─────────

    role_options = compute_role_options(profile.role)

    # Selected role: from the target profile's roles resource
    selected_role: str | None = None
    if profile_ctx.resources["roles"].selected:
        selected_role = profile_ctx.resources["roles"].selected[0].role

    # ── Step 8: Response assembly ────────────────────────────────────────

    # Flags — enriched format
    all_flags = dedupe_by_id(
        profile_ctx.resources["flags"].selected
        + profile_ctx.resources["flags"].suggestions
    )
    profile_flags = [
        ProfileFlagConfig(
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

    current_flag = None
    if profile_ctx.resources["flags"].selected:
        f = profile_ctx.resources["flags"].selected[0]
        current_flag = ProfileFlagConfig(
            key=derive_flag_key_and_label(f.name)[0],
            label=derive_flag_key_and_label(f.name)[1],
            description=f.description,
            icon_id=f.icon,
            flag_option_id=f.id,
            show=show_flags_map.get("flags", True),
            required=required_flags_map.get("flags", False),
            generated=f.generated,
        )

    # Names, Emails, Request Limits — all = selected + suggestions deduped
    all_names = dedupe_by_id(
        profile_ctx.resources["names"].selected
        + profile_ctx.resources["names"].suggestions
    )
    all_emails = dedupe_by_id(
        profile_ctx.resources["emails"].selected
        + profile_ctx.resources["emails"].suggestions
    )
    all_request_limits = dedupe_by_id(
        profile_ctx.resources["request_limits"].selected
        + profile_ctx.resources["request_limits"].suggestions
    )

    # Suggestions maps (IDs only)
    suggestions_map = {
        "names": [n.id for n in profile_ctx.resources["names"].suggestions],
        "emails": [e.id for e in profile_ctx.resources["emails"].suggestions],
        "request_limits": [
            r.id for r in profile_ctx.resources["request_limits"].suggestions
        ],
        "departments": [d.id for d in profile_ctx.resources["departments"].suggestions],
        "roles": [r.id for r in profile_ctx.resources["roles"].suggestions],
    }

    def _section(resource_key: str) -> dict:
        return {
            "show": show_flags_map.get(resource_key, False),
            "required": required_flags_map.get(resource_key, False),
            "suggestions": suggestions_map.get(resource_key, []),
            "show_ai_generate": show_ai_generate_map.get(resource_key, False),
            "tool_id": tool_ids_map.get(resource_key),
        }

    return GetProfileApiResponse(
        actor_name=profile.name,
        profile_exists=profile_ctx.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        draft_version=profile_ctx.draft_version,
        group_id=group_id,
        profile_id=target_profile_id,
        role=selected_role,
        role_options=role_options,
        basic_show_ai_generate=basic_show_ai_generate,
        general_show_ai_generate=general_show_ai_generate,
        names=ProfileNameSection(
            **_section("names"),
            resource=_serialize_model(profile_ctx.resources["names"].selected[0])
            if profile_ctx.resources["names"].selected
            else None,
            resources=_serialize_models(all_names),
        ),
        emails=ProfileEmailSection(
            **_section("emails"),
            current=_serialize_models(profile_ctx.resources["emails"].selected) or None,
            resources=_serialize_models(all_emails),
        ),
        request_limits=ProfileRequestLimitSection(
            **_section("request_limits"),
            resource=_serialize_model(
                profile_ctx.resources["request_limits"].selected[0]
            )
            if profile_ctx.resources["request_limits"].selected
            else None,
            resources=_serialize_models(all_request_limits),
        ),
        flags=ProfileFlagSection(
            **_section("flags"),
            current=current_flag,
            resources=profile_flags,
        ),
        departments=ProfileDepartmentSection(
            **_section("departments"),
            current=_serialize_models(profile_ctx.resources["departments"].selected)
            or None,
            resources=_serialize_models(all_departments),
        ),
        roles=ProfileRoleSection(
            **_section("roles"),
            current=_serialize_models(profile_ctx.resources["roles"].selected) or None,
            resources=_serialize_models(all_roles),
        ),
    )
