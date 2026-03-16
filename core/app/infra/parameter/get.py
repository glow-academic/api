"""Parameter GET endpoint — composable infra architecture.

Uses composable infra layers:
  1. resolve_common_context — profile + tool graph + runs
  2. resolve_parameter_permissions_context — fail-fast 404/403
  3. resolve_parameter_context — artifact + draft → merged + hydrated resources
  4. score_tools — tool graph + artifact resources → per-resource tool picks
  5. Pure Python — permissions, show/required flags, response assembly
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.helpers import dedupe_by_id
from app.infra.parameter.context import resolve_parameter_context
from app.infra.parameter.permissions import (
    PARAMETER_BASIC_RESOURCES,
    PARAMETER_FIELDS_RESOURCES,
    PARAMETER_RESOURCES,
    compute_can_edit,
    compute_departments_required,
    compute_description_required,
    compute_disabled_reason,
    compute_fields_required,
    compute_flag_required,
    compute_name_required,
    compute_show_departments,
    compute_show_description,
    compute_show_fields,
    compute_show_flag,
    compute_show_name,
    has_access,
)
from app.infra.parameter.permissions_context import (
    resolve_parameter_permissions_context,
)
from app.infra.tool_graph import score_tools
from app.infra.parameter.types import (
    GetParameterApiResponse,
    ParameterDepartmentSection,
    ParameterDescriptionSection,
    ParameterFieldSection,
    ParameterFlagConfig,
    ParameterFlagSection,
    ParameterNameSection,
)

# ---------------------------------------------------------------------------
# get_parameter_client — composable infra architecture
# ---------------------------------------------------------------------------


def derive_flag_key_and_label(name: str | None) -> tuple[str, str]:
    """Derive key and label from flag name like 'parameter_active' -> ('active', 'Active')"""
    if not name:
        return ("unknown", "Unknown")
    key = name.replace("parameter_", "")
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


async def get_parameter_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    parameter_id: UUID | None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    bypass_cache: bool = False,
) -> GetParameterApiResponse:
    """Parameter GET using composable infra functions.

    Flow:
      1. resolve_common_context(profile_id) → profile, tool_graph, runs
      2. resolve_parameter_permissions_context → access check (404, 403, fail fast)
      3. resolve_parameter_context(parameter_id, draft_id, ...) → hydrated resources
      4. score_tools(tool_graph, PARAMETER_RESOURCES) → per-resource tool picks
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
        artifact_type="parameter",
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

    perms = None
    if parameter_id is not None:
        async with pool.acquire() as conn:
            perms = await resolve_parameter_permissions_context(conn, parameter_id)

        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Parameter {parameter_id} not found",
            )

        if not has_access(profile.role, profile.department_ids, perms.department_ids):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this parameter. It may be restricted to other departments.",
            )

    # ── Step 3: Parameter artifact context ─────────────────────────────────

    param_ctx = await resolve_parameter_context(
        pool,
        redis,
        parameter_id=parameter_id,
        group_id=group_id,
        draft_id=draft_id,
        user_department_ids=profile.department_ids,
        bypass_cache=bypass_cache,
    )

    # ── Step 4: Tool scoring ─────────────────────────────────────────────

    scores = score_tools(common.tool_graph, PARAMETER_RESOURCES)

    agent_ids: dict[str, UUID | None] = {
        r: (scores.best[r].agent_id if scores.best.get(r) else None)
        for r in PARAMETER_RESOURCES
    }

    tool_ids_map: dict[str, UUID | None] = {
        r: (scores.best[r].tool_id if scores.best.get(r) else None)
        for r in PARAMETER_RESOURCES
    }

    # ── Step 5: Permissions ──────────────────────────────────────────────

    perms_department_ids = perms.department_ids if perms else []
    active_scenario_count = perms.active_scenario_count if perms else 0

    can_edit = compute_can_edit(
        user_role=profile.role,
        parameter_department_ids=perms_department_ids,
        active_scenario_count=active_scenario_count,
        user_department_ids=profile.department_ids,
    )

    disabled_reason = compute_disabled_reason(
        user_role=profile.role,
        parameter_department_ids=perms_department_ids,
        active_scenario_count=active_scenario_count,
        user_department_ids=profile.department_ids,
    )

    # ── Step 6: Show / Required / AI flags ───────────────────────────────

    names_has_tools = scores.has_any.get("names", False)

    all_departments = dedupe_by_id(
        param_ctx.resources["departments"].selected
        + param_ctx.resources["departments"].suggestions
    )
    all_fields = dedupe_by_id(
        param_ctx.resources["fields"].selected
        + param_ctx.resources["fields"].suggestions,
        id_attr="field_id",
    )

    show_flags_map = {
        "names": compute_show_name(names_has_tools),
        "descriptions": compute_show_description(),
        "flags": compute_show_flag(),
        "departments": compute_show_departments(len(all_departments)),
        "fields": compute_show_fields(len(all_fields)),
    }

    required_flags_map = {
        "names": compute_name_required(),
        "descriptions": compute_description_required(),
        "flags": compute_flag_required(),
        "departments": compute_departments_required(),
        "fields": compute_fields_required(),
    }

    def compute_show_ai_generate(resource: str) -> bool:
        return agent_ids.get(resource) is not None

    show_ai_generate_map = {r: compute_show_ai_generate(r) for r in PARAMETER_RESOURCES}

    basic_show_ai_generate = any(
        show_ai_generate_map.get(r, False) for r in PARAMETER_BASIC_RESOURCES
    )
    fields_step_show_ai_generate = any(
        show_ai_generate_map.get(r, False) for r in PARAMETER_FIELDS_RESOURCES
    )

    # ── Step 7: Validation ───────────────────────────────────────────────

    if parameter_id is None:
        if not all_departments:
            raise HTTPException(
                status_code=400, detail="No accessible departments found for user"
            )

    # ── Step 8: Response assembly ────────────────────────────────────────

    # Flags — enriched format
    all_flags = dedupe_by_id(
        param_ctx.resources["flags"].selected + param_ctx.resources["flags"].suggestions
    )
    parameter_flags = [
        ParameterFlagConfig(
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
        ParameterFlagConfig(
            key=derive_flag_key_and_label(f.name)[0],
            label=derive_flag_key_and_label(f.name)[1],
            description=f.description,
            icon_id=f.icon,
            flag_option_id=f.id,
            show=show_flags_map.get("flags", True),
            required=required_flags_map.get("flags", False),
            generated=f.generated,
        )
        for f in param_ctx.resources["flags"].selected
        if f.id
    ]

    # Names, Descriptions — all = selected + suggestions deduped
    all_names = dedupe_by_id(
        param_ctx.resources["names"].selected + param_ctx.resources["names"].suggestions
    )
    all_descriptions = dedupe_by_id(
        param_ctx.resources["descriptions"].selected
        + param_ctx.resources["descriptions"].suggestions
    )

    # Suggestions maps (IDs only)
    suggestions_map = {
        "names": [n.id for n in param_ctx.resources["names"].suggestions],
        "descriptions": [d.id for d in param_ctx.resources["descriptions"].suggestions],
        "departments": [d.id for d in param_ctx.resources["departments"].suggestions],
        "fields": [f.id for f in param_ctx.resources["fields"].suggestions],
    }

    def _section(resource_key: str) -> dict:
        return {
            "show": show_flags_map.get(resource_key, False),
            "required": required_flags_map.get(resource_key, False),
            "suggestions": suggestions_map.get(resource_key, []),
            "show_ai_generate": show_ai_generate_map.get(resource_key, False),
            "tool_id": tool_ids_map.get(resource_key),
        }

    return GetParameterApiResponse(
        actor_name=profile.name,
        parameter_exists=param_ctx.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        draft_version=param_ctx.draft_version,
        group_id=group_id,
        basic_show_ai_generate=basic_show_ai_generate,
        fields_step_show_ai_generate=fields_step_show_ai_generate,
        names=ParameterNameSection(
            **_section("names"),
            resource=_serialize_model(param_ctx.resources["names"].selected[0])
            if param_ctx.resources["names"].selected
            else None,
            resources=_serialize_models(all_names),
        ),
        descriptions=ParameterDescriptionSection(
            **_section("descriptions"),
            resource=_serialize_model(param_ctx.resources["descriptions"].selected[0])
            if param_ctx.resources["descriptions"].selected
            else None,
            resources=_serialize_models(all_descriptions),
        ),
        flags=ParameterFlagSection(
            **_section("flags"),
            current=current_flags or None,
            resources=parameter_flags,
        ),
        departments=ParameterDepartmentSection(
            **_section("departments"),
            current=_serialize_models(param_ctx.resources["departments"].selected)
            or None,
            resources=_serialize_models(all_departments),
        ),
        fields=ParameterFieldSection(
            **_section("fields"),
            current=_serialize_models(param_ctx.resources["fields"].selected) or None,
            resources=_serialize_models(all_fields),
        ),
    )
