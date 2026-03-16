"""Model GET endpoint — composable infra architecture.

Uses composable infra layers:
  1. resolve_common_context — profile + tool graph + runs
  2. resolve_model_permissions_context — fail-fast 404/403
  3. resolve_model_context — artifact + draft → merged + hydrated resources
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
from app.infra.model.context import resolve_model_context
from app.infra.model.permissions import (
    MODEL_BASIC_RESOURCES,
    MODEL_FEATURES_RESOURCES,
    MODEL_PROVIDER_RESOURCES,
    MODEL_RESOURCES,
    compute_can_edit,
    compute_departments_required,
    compute_description_required,
    compute_disabled_reason,
    compute_flag_required,
    compute_modalities_required,
    compute_name_required,
    compute_pricing_required,
    compute_provider_required,
    compute_qualities_required,
    compute_reasoning_levels_required,
    compute_show_departments,
    compute_show_description,
    compute_show_flag,
    compute_show_modalities,
    compute_show_name,
    compute_show_pricing,
    compute_show_provider,
    compute_show_qualities,
    compute_show_reasoning_levels,
    compute_show_temperature_levels,
    compute_show_value,
    compute_show_voices,
    compute_temperature_levels_required,
    compute_value_required,
    compute_voices_required,
    derive_flag_key_and_label,
    has_access,
)
from app.infra.model.permissions_context import resolve_model_permissions_context
from app.infra.tool_graph import score_tools
from app.infra.model.types import (
    GetModelApiResponse,
    ModelDepartmentSection,
    ModelDescriptionSection,
    ModelFlagConfig,
    ModelFlagSection,
    ModelModalitySection,
    ModelNameSection,
    ModelPricingSection,
    ModelProviderSection,
    ModelQualitySection,
    ModelReasoningLevelSection,
    ModelTemperatureLevelSection,
    ModelValueSection,
    ModelVoiceSection,
)

# ---------------------------------------------------------------------------
# get_model_client — composable infra architecture
# ---------------------------------------------------------------------------


async def get_model_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    model_id: UUID | None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    bypass_cache: bool = False,
) -> GetModelApiResponse:
    """Model GET using composable infra functions.

    Flow:
      1. resolve_common_context(profile_id) → profile, tool_graph, runs
      2. resolve_model_permissions_context → access check (404, 403, fail fast)
      3. resolve_model_context(model_id, draft_id, ...) → hydrated resources
      4. score_tools(tool_graph, MODEL_RESOURCES) → per-resource tool picks
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
        artifact_type="model",
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
    if model_id is not None:
        async with pool.acquire() as conn:
            perms = await resolve_model_permissions_context(conn, model_id)

        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Model {model_id} not found",
            )

        if not has_access(profile.role, profile.department_ids, perms.department_ids):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this model. It may be restricted to other departments.",
            )

    # ── Step 3: Model artifact context ────────────────────────────────────

    model_ctx = await resolve_model_context(
        pool,
        redis,
        model_id=model_id,
        group_id=group_id,
        draft_id=draft_id,
        user_department_ids=profile.department_ids,
        bypass_cache=bypass_cache,
    )

    # ── Step 4: Tool scoring ──────────────────────────────────────────────

    scores = score_tools(common.tool_graph, MODEL_RESOURCES)

    agent_ids: dict[str, UUID | None] = {
        r: (scores.best[r].agent_id if scores.best.get(r) else None)
        for r in MODEL_RESOURCES
    }

    tool_ids_map: dict[str, UUID | None] = {
        r: (scores.best[r].tool_id if scores.best.get(r) else None)
        for r in MODEL_RESOURCES
    }

    # ── Step 5: Permissions ───────────────────────────────────────────────

    perms_department_ids = perms.department_ids if perms else []
    active_agent_count = perms.active_agent_count if perms else 0

    can_edit = compute_can_edit(
        user_role=profile.role,
        model_department_ids=perms_department_ids,
        active_agent_count=active_agent_count,
        user_department_ids=profile.department_ids,
    )

    disabled_reason = compute_disabled_reason(
        user_role=profile.role,
        model_department_ids=perms_department_ids,
        active_agent_count=active_agent_count,
    )

    # ── Step 6: Show / Required / AI flags ────────────────────────────────

    names_has_tools = scores.has_any.get("names", False)
    values_has_tools = scores.has_any.get("values", False)

    all_departments = dedupe_by_id(
        model_ctx.resources["departments"].selected
        + model_ctx.resources["departments"].suggestions
    )

    show_flags_map = {
        "names": compute_show_name(names_has_tools),
        "descriptions": compute_show_description(),
        "values": compute_show_value(values_has_tools),
        "providers": compute_show_provider(),
        "flags": compute_show_flag(),
        "departments": compute_show_departments(len(all_departments)),
        "modalities": compute_show_modalities(),
        "temperature_levels": compute_show_temperature_levels(),
        "pricing": compute_show_pricing(),
        "reasoning_levels": compute_show_reasoning_levels(),
        "qualities": compute_show_qualities(),
        "voices": compute_show_voices(),
    }

    required_flags_map = {
        "names": compute_name_required(),
        "descriptions": compute_description_required(),
        "values": compute_value_required(),
        "providers": compute_provider_required(),
        "flags": compute_flag_required(),
        "departments": compute_departments_required(),
        "modalities": compute_modalities_required(),
        "temperature_levels": compute_temperature_levels_required(),
        "pricing": compute_pricing_required(),
        "reasoning_levels": compute_reasoning_levels_required(),
        "qualities": compute_qualities_required(),
        "voices": compute_voices_required(),
    }

    def compute_show_ai_generate(resource: str) -> bool:
        return agent_ids.get(resource) is not None

    show_ai_generate_map = {r: compute_show_ai_generate(r) for r in MODEL_RESOURCES}

    basic_show_ai_generate = any(
        show_ai_generate_map.get(r, False) for r in MODEL_BASIC_RESOURCES
    )
    provider_show_ai_generate = any(
        show_ai_generate_map.get(r, False) for r in MODEL_PROVIDER_RESOURCES
    )
    features_show_ai_generate = any(
        show_ai_generate_map.get(r, False) for r in MODEL_FEATURES_RESOURCES
    )

    # ── Step 7: Validation ────────────────────────────────────────────────

    if model_id is None:
        if not all_departments:
            raise HTTPException(
                status_code=400, detail="No accessible departments found for user"
            )

    # ── Step 8: Response assembly ─────────────────────────────────────────

    # Flags — enriched format
    all_flags = dedupe_by_id(
        model_ctx.resources["flags"].selected + model_ctx.resources["flags"].suggestions
    )
    model_flags = [
        ModelFlagConfig(
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
        ModelFlagConfig(
            key=derive_flag_key_and_label(f.name)[0],
            label=derive_flag_key_and_label(f.name)[1],
            description=f.description,
            icon_id=f.icon,
            flag_option_id=f.id,
            show=show_flags_map.get("flags", True),
            required=required_flags_map.get("flags", False),
            generated=f.generated,
        )
        for f in model_ctx.resources["flags"].selected
        if f.id
    ]

    # Dedupe all resources
    all_names = dedupe_by_id(
        model_ctx.resources["names"].selected + model_ctx.resources["names"].suggestions
    )
    all_descriptions = dedupe_by_id(
        model_ctx.resources["descriptions"].selected
        + model_ctx.resources["descriptions"].suggestions
    )
    all_values = dedupe_by_id(
        model_ctx.resources["values"].selected
        + model_ctx.resources["values"].suggestions
    )
    all_providers = dedupe_by_id(
        model_ctx.resources["providers"].selected
        + model_ctx.resources["providers"].suggestions
    )
    all_modalities = dedupe_by_id(
        model_ctx.resources["modalities"].selected
        + model_ctx.resources["modalities"].suggestions
    )
    all_temperature_levels = dedupe_by_id(
        model_ctx.resources["temperature_levels"].selected
        + model_ctx.resources["temperature_levels"].suggestions
    )
    all_pricing = dedupe_by_id(
        model_ctx.resources["pricing"].selected
        + model_ctx.resources["pricing"].suggestions
    )
    all_reasoning_levels = dedupe_by_id(
        model_ctx.resources["reasoning_levels"].selected
        + model_ctx.resources["reasoning_levels"].suggestions
    )
    all_qualities = dedupe_by_id(
        model_ctx.resources["qualities"].selected
        + model_ctx.resources["qualities"].suggestions
    )
    all_voices = dedupe_by_id(
        model_ctx.resources["voices"].selected
        + model_ctx.resources["voices"].suggestions
    )

    # Suggestions maps (IDs only)
    suggestions_map = {
        "names": [n.id for n in model_ctx.resources["names"].suggestions],
        "descriptions": [d.id for d in model_ctx.resources["descriptions"].suggestions],
        "values": [v.id for v in model_ctx.resources["values"].suggestions],
        "departments": [d.id for d in model_ctx.resources["departments"].suggestions],
        "modalities": [m.id for m in model_ctx.resources["modalities"].suggestions],
        "temperature_levels": [
            t.id for t in model_ctx.resources["temperature_levels"].suggestions
        ],
        "pricing": [p.id for p in model_ctx.resources["pricing"].suggestions],
        "reasoning_levels": [
            r.id for r in model_ctx.resources["reasoning_levels"].suggestions
        ],
        "qualities": [q.id for q in model_ctx.resources["qualities"].suggestions],
        "voices": [v.id for v in model_ctx.resources["voices"].suggestions],
    }

    def _section(resource_key: str) -> dict:
        return {
            "show": show_flags_map.get(resource_key, False),
            "required": required_flags_map.get(resource_key, False),
            "suggestions": suggestions_map.get(resource_key, []),
            "show_ai_generate": show_ai_generate_map.get(resource_key, False),
            "tool_id": tool_ids_map.get(resource_key),
        }

    return GetModelApiResponse(
        actor_name=profile.name,
        model_exists=model_ctx.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        draft_version=model_ctx.draft_version,
        group_id=group_id,
        basic_show_ai_generate=basic_show_ai_generate,
        provider_show_ai_generate=provider_show_ai_generate,
        features_show_ai_generate=features_show_ai_generate,
        names=ModelNameSection(
            **_section("names"),
            resource=model_ctx.resources["names"].selected[0]
            if model_ctx.resources["names"].selected
            else None,
            resources=all_names,
        ),
        descriptions=ModelDescriptionSection(
            **_section("descriptions"),
            resource=model_ctx.resources["descriptions"].selected[0]
            if model_ctx.resources["descriptions"].selected
            else None,
            resources=all_descriptions,
        ),
        values=ModelValueSection(
            **_section("values"),
            resource=model_ctx.resources["values"].selected[0]
            if model_ctx.resources["values"].selected
            else None,
            resources=all_values,
        ),
        providers=ModelProviderSection(
            **_section("providers"),
            resource=model_ctx.resources["providers"].selected[0]
            if model_ctx.resources["providers"].selected
            else None,
            resources=all_providers,
        ),
        flags=ModelFlagSection(
            **_section("flags"),
            current=current_flags or None,
            resources=model_flags,
        ),
        departments=ModelDepartmentSection(
            **_section("departments"),
            current=model_ctx.resources["departments"].selected or None,
            resources=all_departments,
        ),
        modalities=ModelModalitySection(
            **_section("modalities"),
            current=model_ctx.resources["modalities"].selected or None,
            resources=all_modalities,
        ),
        temperature_levels=ModelTemperatureLevelSection(
            **_section("temperature_levels"),
            current=model_ctx.resources["temperature_levels"].selected or None,
            resources=all_temperature_levels,
        ),
        pricing=ModelPricingSection(
            **_section("pricing"),
            current=model_ctx.resources["pricing"].selected or None,
            resources=all_pricing,
        ),
        reasoning_levels=ModelReasoningLevelSection(
            **_section("reasoning_levels"),
            current=model_ctx.resources["reasoning_levels"].selected or None,
            resources=all_reasoning_levels,
        ),
        qualities=ModelQualitySection(
            **_section("qualities"),
            current=model_ctx.resources["qualities"].selected or None,
            resources=all_qualities,
        ),
        voices=ModelVoiceSection(
            **_section("voices"),
            current=model_ctx.resources["voices"].selected or None,
            resources=all_voices,
        ),
    )
