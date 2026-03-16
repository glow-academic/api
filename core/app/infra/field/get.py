"""Field GET endpoint — composable infra architecture.

Uses composable infra layers:
  1. resolve_common_context — profile + tool graph + runs
  2. resolve_field_permissions_context — access check (404, 403, fail fast)
  3. resolve_field_context — artifact + draft → merged + hydrated resources
  4. score_tools — tool graph + artifact resources → per-resource tool picks
  5. Pure Python — permissions, show/required flags, response assembly
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.field.context import resolve_field_context
from app.infra.field.permissions import (
    FIELD_BASIC_RESOURCES,
    FIELD_RESOURCES,
    compute_can_edit,
    compute_conditional_parameters_required,
    compute_departments_required,
    compute_description_required,
    compute_disabled_reason,
    compute_flag_required,
    compute_name_required,
    compute_show_conditional_parameters,
    compute_show_departments,
    compute_show_description,
    compute_show_flag,
    compute_show_name,
    has_access,
)
from app.infra.field.permissions_context import resolve_field_permissions_context
from app.infra.helpers import dedupe_by_id
from app.infra.tool_graph import score_tools
from app.infra.field.types import (
    FieldConditionalParameterSection,
    FieldDepartmentSection,
    FieldDescriptionSection,
    FieldFlagConfig,
    FieldFlagSection,
    FieldNameSection,
    GetFieldApiResponse,
)

# ---------------------------------------------------------------------------
# get_field_client — composable infra architecture
# ---------------------------------------------------------------------------


def derive_flag_key_and_label(name: str | None) -> tuple[str, str]:
    if not name:
        return ("unknown", "Unknown")
    key = name.replace("field_", "")
    return (key, key.replace("_", " ").title())


async def get_field_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    field_id: UUID | None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    descriptions_search: str | None = None,
    conditional_parameter_search: str | None = None,
    conditional_parameter_show_selected: bool | None = None,
    bypass_cache: bool = False,
) -> GetFieldApiResponse:
    """Field GET using composable infra functions.

    Flow:
      1. resolve_common_context(profile_id) → profile, tool_graph, runs
      2. resolve_field_permissions_context → access check (404, 403, fail fast)
      3. resolve_field_context(field_id, draft_id, ...) → hydrated resources
      4. score_tools(tool_graph, FIELD_RESOURCES) → per-resource tool picks
      5. Pure Python: permissions, show/required/AI flags, response assembly
    """

    # ── Step 1: Common context (profile → tool_graph + runs) ──────────────

    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        draft_id=draft_id,
        artifact_type="field",
        bypass_cache=bypass_cache,
    )

    if common is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    group_id = group_id or common.profile.group_id
    profile = common.profile

    # ── Step 2: Permissions check (fail fast before full hydration) ────────

    perms = None
    if field_id is not None:
        async with pool.acquire() as conn:
            perms = await resolve_field_permissions_context(conn, field_id)

        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Field {field_id} not found",
            )

        if not has_access(profile.role, profile.department_ids, perms.department_ids):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this field. "
                "It may be restricted to other departments.",
            )

    # ── Step 3: Field artifact context ─────────────────────────────────

    field = await resolve_field_context(
        pool,
        redis,
        field_id=field_id,
        group_id=group_id,
        draft_id=draft_id,
        user_department_ids=profile.department_ids,
        descriptions_search=descriptions_search,
        conditional_parameter_search=conditional_parameter_search,
        conditional_parameter_show_selected=conditional_parameter_show_selected,
        bypass_cache=bypass_cache,
    )

    # ── Step 4: Tool scoring ──────────────────────────────────────────────

    scores = score_tools(common.tool_graph, FIELD_RESOURCES)

    tool_ids_map: dict[str, UUID | None] = {
        r: (scores.best[r].tool_id if scores.best.get(r) else None)
        for r in FIELD_RESOURCES
    }

    # ── Step 5: Permissions ───────────────────────────────────────────────

    field_department_ids = [
        d.id for d in field.resources["departments"].selected if d.id
    ]

    can_edit = compute_can_edit(
        user_role=profile.role,
        field_department_ids=field_department_ids,
        user_department_ids=profile.department_ids,
    )

    disabled_reason = compute_disabled_reason(
        user_role=profile.role,
        field_department_ids=field_department_ids,
        user_department_ids=profile.department_ids,
    )

    # ── Step 6: Show / Required / AI flags ────────────────────────────────

    all_departments = dedupe_by_id(
        field.resources["departments"].selected
        + field.resources["departments"].suggestions
    )
    all_conditional_parameters = dedupe_by_id(
        field.resources["conditional_parameters"].selected
        + field.resources["conditional_parameters"].suggestions
    )

    # Validate new mode
    if field_id is None and not all_departments:
        raise HTTPException(
            status_code=400, detail="No accessible departments found for user"
        )

    names_has_tools = scores.has_any.get("names", False)

    show_flags_map = {
        "names": compute_show_name(names_has_tools),
        "descriptions": compute_show_description(),
        "flags": compute_show_flag(),
        "departments": compute_show_departments(len(all_departments)),
        "conditional_parameters": compute_show_conditional_parameters(
            len(all_conditional_parameters)
        ),
    }

    required_flags_map = {
        "names": compute_name_required(),
        "descriptions": compute_description_required(),
        "flags": compute_flag_required(),
        "departments": compute_departments_required(),
        "conditional_parameters": compute_conditional_parameters_required(),
    }

    show_ai_generate_map = {r: scores.best.get(r) is not None for r in FIELD_RESOURCES}

    basic_show_ai_generate = any(
        show_ai_generate_map.get(r, False) for r in FIELD_BASIC_RESOURCES
    )

    suggestions_map: dict[str, list[UUID]] = {
        "names": [n.id for n in field.resources["names"].suggestions],
        "descriptions": [d.id for d in field.resources["descriptions"].suggestions],
        "departments": [d.id for d in field.resources["departments"].suggestions],
        "conditional_parameters": [
            p.id for p in field.resources["conditional_parameters"].suggestions if p.id
        ],
    }

    def _section(resource_key: str) -> dict:
        return {
            "show": show_flags_map.get(resource_key, False),
            "required": required_flags_map.get(resource_key, False),
            "suggestions": suggestions_map.get(resource_key),
            "show_ai_generate": show_ai_generate_map.get(resource_key, False),
            "tool_id": tool_ids_map.get(resource_key),
        }

    # ── Step 7: Resource conversion + response assembly ───────────────────

    # Names + Descriptions
    all_names = dedupe_by_id(
        field.resources["names"].selected + field.resources["names"].suggestions
    )
    all_descriptions = dedupe_by_id(
        field.resources["descriptions"].selected
        + field.resources["descriptions"].suggestions
    )

    # Flags — enriched format
    all_flags_raw = dedupe_by_id(
        field.resources["flags"].selected + field.resources["flags"].suggestions
    )
    all_flags = [
        FieldFlagConfig(
            key=derive_flag_key_and_label(f.name)[0],
            label=derive_flag_key_and_label(f.name)[1],
            description=f.description,
            icon_id=f.icon,
            flag_option_id=f.id,
            show=show_flags_map["flags"],
            required=required_flags_map["flags"],
            generated=f.generated,
        )
        for f in all_flags_raw
        if f.id
    ]

    flag_ids_set = {f.id for f in field.resources["flags"].selected}
    selected_flag = next(
        (f for f in all_flags if f.flag_option_id in flag_ids_set), None
    )

    return GetFieldApiResponse(
        # Context
        actor_name=profile.name,
        field_exists=field.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        draft_version=field.draft_version,
        group_id=group_id,
        # Step-level AI generation flags
        basic_show_ai_generate=basic_show_ai_generate,
        # Per-resource sections
        names=FieldNameSection(
            **_section("names"),
            resource=field.resources["names"].selected[0]
            if field.resources["names"].selected
            else None,
            resources=all_names,
        ),
        descriptions=FieldDescriptionSection(
            **_section("descriptions"),
            resource=field.resources["descriptions"].selected[0]
            if field.resources["descriptions"].selected
            else None,
            resources=all_descriptions,
        ),
        flags=FieldFlagSection(
            **_section("flags"),
            resource=selected_flag,
            resources=all_flags,
        ),
        departments=FieldDepartmentSection(
            **_section("departments"),
            current=[d for d in field.resources["departments"].selected],
            resources=all_departments,
        ),
        conditional_parameters=FieldConditionalParameterSection(
            **_section("conditional_parameters"),
            current=field.resources["conditional_parameters"].selected,
            resources=all_conditional_parameters,
        ),
    )
