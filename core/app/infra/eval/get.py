"""Eval GET endpoint — composable infra architecture.

Uses composable infra layers:
  1. resolve_common_context — profile + tool graph + runs
  2. resolve_eval_permissions_context — fail-fast 404/403
  3. resolve_eval_context — artifact + draft -> merged + hydrated resources
  4. score_tools — tool graph + artifact resources -> per-resource tool picks
  5. Pure Python — permissions, show/required flags, response assembly
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.eval.context import resolve_eval_context
from app.infra.eval.permissions import (
    EVAL_BASIC_RESOURCES,
    EVAL_MODEL_RESOURCES,
    EVAL_RESOURCES,
    compute_active_flag_required,
    compute_can_edit,
    compute_departments_required,
    compute_description_required,
    compute_disabled_reason,
    compute_model_flags_required,
    compute_model_positions_required,
    compute_model_rubrics_required,
    compute_models_required,
    compute_name_required,
    compute_show_active_flag,
    compute_show_departments,
    compute_show_description,
    compute_show_model_flags,
    compute_show_model_positions,
    compute_show_model_rubrics,
    compute_show_models,
    compute_show_name,
    has_access,
)
from app.infra.eval.permissions_context import resolve_eval_permissions_context
from app.infra.helpers import dedupe_by_id
from app.infra.tool_graph import score_tools
from app.infra.eval.types import (
    EvalDepartmentSection,
    EvalDescriptionSection,
    EvalFlagConfig,
    EvalFlagSection,
    EvalModelFlagSection,
    EvalModelPositionSection,
    EvalModelRubricSection,
    EvalModelSection,
    EvalNameSection,
    GetEvalApiResponse,
)

# ---------------------------------------------------------------------------
# get_eval_client — composable infra architecture
# ---------------------------------------------------------------------------


def derive_flag_key_and_label(name: str | None) -> tuple[str, str]:
    """Derive key and label from flag name like 'eval_active' -> ('active', 'Active')"""
    if not name:
        return ("unknown", "Unknown")
    key = name.replace("eval_", "")
    label = key.replace("_", " ").title()
    return (key, label)


async def get_eval_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    eval_id: UUID | None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    bypass_cache: bool = False,
) -> GetEvalApiResponse:
    """Eval GET using composable infra functions.

    Flow:
      1. resolve_common_context(profile_id) -> profile, tool_graph, runs
      2. resolve_eval_permissions_context -> access check (404, 403, fail fast)
      3. resolve_eval_context(eval_id, draft_id, ...) -> hydrated resources
      4. score_tools(tool_graph, EVAL_RESOURCES) -> per-resource tool picks
      5. Pure Python: permissions, show/required/AI flags, response assembly
    """

    # -- Step 1: Common context (profile -> tool_graph + runs) --

    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        draft_id=draft_id,
        artifact_type="eval",
        bypass_cache=bypass_cache,
    )

    if common is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    group_id = group_id or common.profile.group_id
    profile = common.profile

    # -- Step 2: Permissions check (fail fast before full hydration) --

    perms = None
    if eval_id is not None:
        async with pool.acquire() as conn:
            perms = await resolve_eval_permissions_context(conn, eval_id)

        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Eval {eval_id} not found",
            )

        if not has_access(profile.role, profile.department_ids, perms.department_ids):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this eval. It may be restricted to other departments.",
            )

    # -- Step 3: Eval artifact context --

    eval_ctx = await resolve_eval_context(
        pool,
        redis,
        eval_id=eval_id,
        group_id=group_id,
        draft_id=draft_id,
        user_department_ids=profile.department_ids,
        bypass_cache=bypass_cache,
    )

    # -- Step 4: Tool scoring --

    scores = score_tools(common.tool_graph, EVAL_RESOURCES)

    tool_ids_map: dict[str, UUID | None] = {
        r: (scores.best[r].tool_id if scores.best.get(r) else None)
        for r in EVAL_RESOURCES
    }

    # -- Step 5: Permissions --

    can_edit = compute_can_edit(user_role=profile.role)
    disabled_reason = compute_disabled_reason(user_role=profile.role)

    # -- Step 6: Show / Required / AI flags --

    names_has_tools = scores.has_any.get("names", False)

    all_departments = dedupe_by_id(
        eval_ctx.resources["departments"].selected
        + eval_ctx.resources["departments"].suggestions
    )
    all_models = dedupe_by_id(eval_ctx.resources["models"].selected)
    all_model_flags = dedupe_by_id(
        eval_ctx.resources["model_flags"].selected
        + eval_ctx.resources["model_flags"].suggestions
    )
    all_model_rubrics = dedupe_by_id(
        eval_ctx.resources["model_rubrics"].selected
        + eval_ctx.resources["model_rubrics"].suggestions
    )
    all_model_positions = dedupe_by_id(
        eval_ctx.resources["model_positions"].selected
        + eval_ctx.resources["model_positions"].suggestions
    )

    show_flags_map = {
        "names": compute_show_name(names_has_tools),
        "descriptions": compute_show_description(),
        "flags": compute_show_active_flag(),
        "departments": compute_show_departments(len(all_departments)),
        "models": compute_show_models(len(all_models)),
        "model_flags": compute_show_model_flags(len(all_model_flags)),
        "model_rubrics": compute_show_model_rubrics(len(all_model_rubrics)),
        "model_positions": compute_show_model_positions(len(all_model_positions)),
    }

    required_flags_map = {
        "names": compute_name_required(),
        "descriptions": compute_description_required(),
        "flags": compute_active_flag_required(),
        "departments": compute_departments_required(show_flags_map["departments"]),
        "models": compute_models_required(),
        "model_flags": compute_model_flags_required(),
        "model_rubrics": compute_model_rubrics_required(),
        "model_positions": compute_model_positions_required(),
    }

    show_ai_generate_map = {r: scores.best.get(r) is not None for r in EVAL_RESOURCES}

    basic_show_ai_generate = any(
        show_ai_generate_map.get(r, False) for r in EVAL_BASIC_RESOURCES
    )
    model_show_ai_generate = any(
        show_ai_generate_map.get(r, False) for r in EVAL_MODEL_RESOURCES
    )

    # -- Step 7: Validation --

    if eval_id is None:
        if not all_departments:
            raise HTTPException(
                status_code=400, detail="No accessible departments found for user"
            )

    # -- Step 8: Response assembly --

    # Flags — enriched format
    all_flags = dedupe_by_id(
        eval_ctx.resources["flags"].selected + eval_ctx.resources["flags"].suggestions
    )
    eval_flags = [
        EvalFlagConfig(
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

    # Find specific flags from selected
    selected_flag_ids = {f.id for f in eval_ctx.resources["flags"].selected}
    active_flag = next(
        (
            EvalFlagConfig(
                key=derive_flag_key_and_label(f.name)[0],
                label=derive_flag_key_and_label(f.name)[1],
                description=f.description,
                icon_id=f.icon,
                flag_option_id=f.id,
                show=show_flags_map.get("flags", True),
                required=required_flags_map.get("flags", False),
                generated=f.generated,
            )
            for f in eval_ctx.resources["flags"].selected
            if f.id and getattr(f, "name", "") == "eval_active"
        ),
        None,
    )
    dynamic_flag = next(
        (
            EvalFlagConfig(
                key=derive_flag_key_and_label(f.name)[0],
                label=derive_flag_key_and_label(f.name)[1],
                description=f.description,
                icon_id=f.icon,
                flag_option_id=f.id,
                show=True,
                required=False,
                generated=f.generated,
            )
            for f in eval_ctx.resources["flags"].selected
            if f.id and getattr(f, "name", "") == "dynamic"
        ),
        None,
    )
    groups_flag = next(
        (
            EvalFlagConfig(
                key=derive_flag_key_and_label(f.name)[0],
                label=derive_flag_key_and_label(f.name)[1],
                description=f.description,
                icon_id=f.icon,
                flag_option_id=f.id,
                show=True,
                required=False,
                generated=f.generated,
            )
            for f in eval_ctx.resources["flags"].selected
            if f.id and getattr(f, "name", "") not in {"eval_active", "dynamic"}
        ),
        None,
    )

    # Names, Descriptions — all = selected + suggestions deduped
    all_names = dedupe_by_id(
        eval_ctx.resources["names"].selected + eval_ctx.resources["names"].suggestions
    )
    all_descriptions = dedupe_by_id(
        eval_ctx.resources["descriptions"].selected
        + eval_ctx.resources["descriptions"].suggestions
    )

    # Suggestions maps (IDs only)
    suggestions_map: dict[str, list[UUID]] = {
        "names": [n.id for n in eval_ctx.resources["names"].suggestions],
        "descriptions": [d.id for d in eval_ctx.resources["descriptions"].suggestions],
        "departments": [d.id for d in eval_ctx.resources["departments"].suggestions],
    }

    def _section(resource_key: str) -> dict:
        return {
            "show": show_flags_map.get(resource_key, False),
            "required": required_flags_map.get(resource_key, False),
            "suggestions": suggestions_map.get(resource_key),
            "show_ai_generate": show_ai_generate_map.get(resource_key, False),
            "tool_id": tool_ids_map.get(resource_key),
        }

    return GetEvalApiResponse(
        actor_name=profile.name,
        eval_exists=eval_ctx.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        draft_version=eval_ctx.draft_version,
        group_id=group_id,
        basic_show_ai_generate=basic_show_ai_generate,
        model_show_ai_generate=model_show_ai_generate,
        names=EvalNameSection(
            **_section("names"),
            resource=eval_ctx.resources["names"].selected[0]
            if eval_ctx.resources["names"].selected
            else None,
            resources=all_names,
        ),
        descriptions=EvalDescriptionSection(
            **_section("descriptions"),
            resource=eval_ctx.resources["descriptions"].selected[0]
            if eval_ctx.resources["descriptions"].selected
            else None,
            resources=all_descriptions,
        ),
        active_flags=EvalFlagSection(
            **_section("flags"),
            resource=active_flag,
            resources=eval_flags,
        ),
        dynamic_flags=EvalFlagSection(
            show=True,
            required=False,
            show_ai_generate=show_ai_generate_map.get("flags", False),
            tool_id=tool_ids_map.get("flags"),
            resource=dynamic_flag,
            resources=eval_flags,
        ),
        groups_flags=EvalFlagSection(
            show=True,
            required=False,
            show_ai_generate=show_ai_generate_map.get("flags", False),
            tool_id=tool_ids_map.get("flags"),
            resource=groups_flag,
            resources=eval_flags,
        ),
        departments=EvalDepartmentSection(
            **_section("departments"),
            current=eval_ctx.resources["departments"].selected or None,
            resources=all_departments,
        ),
        models=EvalModelSection(
            **_section("models"),
            current=eval_ctx.resources["models"].selected or None,
            resources=all_models,
        ),
        model_flags=EvalModelFlagSection(
            **_section("model_flags"),
            current=eval_ctx.resources["model_flags"].selected or None,
            resources=all_model_flags,
        ),
        model_rubrics=EvalModelRubricSection(
            **_section("model_rubrics"),
            current=eval_ctx.resources["model_rubrics"].selected or None,
            resources=all_model_rubrics,
        ),
        model_positions=EvalModelPositionSection(
            **_section("model_positions"),
            current=eval_ctx.resources["model_positions"].selected or None,
            resources=all_model_positions,
        ),
    )


# ---------------------------------------------------------------------------
# Route handler
# ---------------------------------------------------------------------------
