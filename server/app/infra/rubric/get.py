"""Canonical shared rubric get operation.

Uses composable infra layers:
  1. resolve_common_context — profile + tool graph + runs
  2. resolve_rubric_permissions_context — fail-fast 404/403
  3. resolve_rubric_context — artifact + draft -> merged + hydrated resources
  4. score_tools — tool graph + artifact resources -> per-resource tool picks
  5. Pure Python — permissions, show/required flags, response assembly
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.helpers import dedupe_by_id
from app.infra.rubric.context import resolve_rubric_context
from app.infra.rubric.permissions import (
    RUBRIC_BASIC_RESOURCES,
    RUBRIC_CONTENT_RESOURCES,
    RUBRIC_RESOURCES,
    compute_can_edit,
    compute_departments_required,
    compute_description_required,
    compute_disabled_reason,
    compute_flag_required,
    compute_name_required,
    compute_points_required,
    compute_show_departments,
    compute_show_description,
    compute_show_flag,
    compute_show_name,
    compute_show_points,
    compute_show_standard_groups,
    compute_show_standards,
    compute_standard_groups_required,
    compute_standards_required,
    has_access,
)
from app.infra.rubric.permissions_context import resolve_rubric_permissions_context
from app.infra.tool_graph import score_tools
from app.infra.rubric.types import (
    GetRubricApiResponse,
    RubricDepartmentSection,
    RubricDescriptionSection,
    RubricFlagConfig,
    RubricFlagSection,
    RubricNameSection,
    RubricPointsSection,
    RubricStandardGroupsSection,
    RubricStandardsSection,
)

# ---------------------------------------------------------------------------
# get_rubric_impl — composable infra architecture
# ---------------------------------------------------------------------------


def derive_flag_key_and_label(name: str | None) -> tuple[str, str]:
    """Derive key and label from flag name like 'rubric_active' -> ('active', 'Active')"""
    if not name:
        return ("unknown", "Unknown")
    key = name.replace("rubric_", "")
    label = key.replace("_", " ").title()
    return (key, label)


async def get_rubric_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    rubric_id: UUID | None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    bypass_cache: bool = False,
) -> GetRubricApiResponse:
    """Rubric GET using composable infra functions.

    Flow:
      1. resolve_common_context(profile_id) -> profile, tool_graph, runs
      2. resolve_rubric_permissions_context -> access check (404, 403, fail fast)
      3. resolve_rubric_context(rubric_id, draft_id, ...) -> hydrated resources
      4. score_tools(tool_graph, RUBRIC_RESOURCES) -> per-resource tool picks
      5. Pure Python: permissions, show/required/AI flags, response assembly
    """

    # -- Step 1: Common context (profile -> tool_graph + runs) ----------------

    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        draft_id=draft_id,
        artifact_type="rubric",
        bypass_cache=bypass_cache,
    )

    if common is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    group_id = group_id or common.profile.group_id
    profile = common.profile

    # -- Step 2: Permissions check (fail fast before full hydration) -----------

    perms = None
    if rubric_id is not None:
        async with pool.acquire() as conn:
            perms = await resolve_rubric_permissions_context(conn, rubric_id)

        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Rubric {rubric_id} not found",
            )

        if not has_access(profile.role, profile.department_ids, perms.department_ids):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this rubric. It may be restricted to other departments.",
            )

    # -- Step 3: Rubric artifact context --------------------------------------

    rubric_ctx = await resolve_rubric_context(
        pool,
        redis,
        rubric_id=rubric_id,
        group_id=group_id,
        draft_id=draft_id,
        user_department_ids=profile.department_ids,
        bypass_cache=bypass_cache,
    )

    # -- Step 4: Tool scoring -------------------------------------------------

    scores = score_tools(common.tool_graph, RUBRIC_RESOURCES)

    agent_ids: dict[str, UUID | None] = {
        r: (scores.best[r].agent_id if scores.best.get(r) else None)
        for r in RUBRIC_RESOURCES
    }

    tool_ids_map: dict[str, UUID | None] = {
        r: (scores.best[r].tool_id if scores.best.get(r) else None)
        for r in RUBRIC_RESOURCES
    }

    # -- Step 5: Permissions --------------------------------------------------

    perms_department_ids = perms.department_ids if perms else []
    active_simulation_count = perms.active_simulation_count if perms else 0

    can_edit = compute_can_edit(
        user_role=profile.role,
        rubric_department_ids=perms_department_ids,
        active_simulation_count=active_simulation_count,
    )

    disabled_reason = compute_disabled_reason(
        user_role=profile.role,
        rubric_department_ids=perms_department_ids,
        active_simulation_count=active_simulation_count,
    )

    # -- Step 6: Show / Required / AI flags -----------------------------------

    names_has_tools = scores.has_any.get("names", False)

    all_departments = dedupe_by_id(
        rubric_ctx.resources["departments"].selected
        + rubric_ctx.resources["departments"].suggestions
    )
    all_standard_groups = dedupe_by_id(
        rubric_ctx.resources["standard_groups"].selected
        + rubric_ctx.resources["standard_groups"].suggestions
    )

    show_flags_map = {
        "names": compute_show_name(names_has_tools),
        "descriptions": compute_show_description(),
        "flags": compute_show_flag(),
        "departments": compute_show_departments(len(all_departments)),
        "points": compute_show_points(),
        "standard_groups": compute_show_standard_groups(),
        "standards": compute_show_standards(len(all_standard_groups)),
    }

    required_flags_map = {
        "names": compute_name_required(),
        "descriptions": compute_description_required(),
        "flags": compute_flag_required(),
        "departments": compute_departments_required(),
        "points": compute_points_required(),
        "standard_groups": compute_standard_groups_required(),
        "standards": compute_standards_required(),
    }

    def compute_show_ai_generate(resource: str) -> bool:
        return agent_ids.get(resource) is not None

    show_ai_generate_map = {r: compute_show_ai_generate(r) for r in RUBRIC_RESOURCES}

    basic_show_ai_generate = any(
        show_ai_generate_map.get(r, False) for r in RUBRIC_BASIC_RESOURCES
    )
    content_show_ai_generate = any(
        show_ai_generate_map.get(r, False) for r in RUBRIC_CONTENT_RESOURCES
    )

    # -- Step 7: Validation ---------------------------------------------------

    if rubric_id is None:
        if not all_departments:
            raise HTTPException(
                status_code=400, detail="No accessible departments found for user"
            )

    # -- Step 8: Response assembly --------------------------------------------

    # Flags — enriched format
    all_flags = dedupe_by_id(
        rubric_ctx.resources["flags"].selected
        + rubric_ctx.resources["flags"].suggestions
    )
    rubric_flags = [
        RubricFlagConfig(
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
        RubricFlagConfig(
            key=derive_flag_key_and_label(f.name)[0],
            label=derive_flag_key_and_label(f.name)[1],
            description=f.description,
            icon_id=f.icon,
            flag_option_id=f.id,
            show=show_flags_map.get("flags", True),
            required=required_flags_map.get("flags", False),
            generated=f.generated,
        )
        for f in rubric_ctx.resources["flags"].selected
        if f.id
    ]

    # Names, Descriptions — all = selected + suggestions deduped
    all_names = dedupe_by_id(
        rubric_ctx.resources["names"].selected
        + rubric_ctx.resources["names"].suggestions
    )
    all_descriptions = dedupe_by_id(
        rubric_ctx.resources["descriptions"].selected
        + rubric_ctx.resources["descriptions"].suggestions
    )
    all_points = dedupe_by_id(
        rubric_ctx.resources["points"].selected
        + rubric_ctx.resources["points"].suggestions
    )

    # Suggestions maps (IDs only)
    suggestions_map = {
        "names": [n.id for n in rubric_ctx.resources["names"].suggestions],
        "descriptions": [
            d.id for d in rubric_ctx.resources["descriptions"].suggestions
        ],
        "departments": [d.id for d in rubric_ctx.resources["departments"].suggestions],
        "points": [p.id for p in rubric_ctx.resources["points"].suggestions],
        "standard_groups": [
            sg.id for sg in rubric_ctx.resources["standard_groups"].suggestions
        ],
        "standards": [s.id for s in rubric_ctx.resources["standards"].suggestions],
    }

    def _section(resource_key: str) -> dict:
        return {
            "show": show_flags_map.get(resource_key, False),
            "required": required_flags_map.get(resource_key, False),
            "suggestions": suggestions_map.get(resource_key, []),
            "show_ai_generate": show_ai_generate_map.get(resource_key, False),
            "tool_id": tool_ids_map.get(resource_key),
        }

    return GetRubricApiResponse(
        actor_name=profile.name,
        rubric_exists=rubric_ctx.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        draft_version=rubric_ctx.draft_version,
        group_id=group_id,
        basic_show_ai_generate=basic_show_ai_generate,
        content_show_ai_generate=content_show_ai_generate,
        names=RubricNameSection(
            **_section("names"),
            resource=rubric_ctx.resources["names"].selected[0]
            if rubric_ctx.resources["names"].selected
            else None,
            resources=all_names,
        ),
        descriptions=RubricDescriptionSection(
            **_section("descriptions"),
            resource=rubric_ctx.resources["descriptions"].selected[0]
            if rubric_ctx.resources["descriptions"].selected
            else None,
            resources=all_descriptions,
        ),
        flags=RubricFlagSection(
            **_section("flags"),
            current=current_flags or None,
            resources=rubric_flags,
        ),
        departments=RubricDepartmentSection(
            **_section("departments"),
            current=rubric_ctx.resources["departments"].selected or None,
            resources=all_departments,
        ),
        points=RubricPointsSection(
            **_section("points"),
            resource=rubric_ctx.resources["points"].selected[0]
            if rubric_ctx.resources["points"].selected
            else None,
            resources=all_points,
        ),
        standard_groups=RubricStandardGroupsSection(
            **_section("standard_groups"),
            current=rubric_ctx.resources["standard_groups"].selected or None,
            resources=all_standard_groups,
        ),
        standards=RubricStandardsSection(
            **_section("standards"),
            current=rubric_ctx.resources["standards"].selected or None,
            resources=dedupe_by_id(
                rubric_ctx.resources["standards"].selected
                + rubric_ctx.resources["standards"].suggestions
            ),
        ),
    )
