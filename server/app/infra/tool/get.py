"""Canonical shared tool get operation.

Uses composable infra layers:
  1. resolve_common_context — profile + tool graph + runs
  2. resolve_tool_permissions_context — fail-fast 404/403
  3. resolve_tool_artifact_context — artifact + draft → merged + hydrated resources
  4. score_tools — tool graph + artifact resources → per-resource tool picks
  5. Pure Python — permissions, show/required flags, response assembly
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.helpers import dedupe_by_id
from app.infra.tool.context import resolve_tool_artifact_context
from app.infra.tool.permissions import (
    TOOL_RESOURCES,
    compute_args_outputs_required,
    compute_args_required,
    compute_artifacts_required,
    compute_can_edit,
    compute_description_required,
    compute_disabled_reason,
    compute_flag_required,
    compute_name_required,
    compute_operations_required,
    compute_show_arg_positions,
    compute_show_args,
    compute_show_args_outputs,
    compute_show_artifacts,
    compute_show_description,
    compute_show_flag,
    compute_show_name,
    compute_show_operations,
    has_access,
)
from app.infra.tool.permissions_context import (
    resolve_tool_permissions_context,
)
from app.infra.tool_graph import score_tools
from app.infra.tool.types import (
    GetToolApiResponse,
    ToolArgOutputSection,
    ToolArgPositionSection,
    ToolArgSection,
    ToolArtifactSection,
    ToolDescriptionSection,
    ToolFlagConfig,
    ToolFlagSection,
    ToolNameSection,
    ToolOperationSection,
)

# ---------------------------------------------------------------------------
# get_tool_impl — composable infra architecture
# ---------------------------------------------------------------------------


def derive_flag_key_and_label(name: str | None) -> tuple[str, str]:
    """Derive key and label from flag name like 'tool_active' -> ('active', 'Active')"""
    if not name:
        return ("unknown", "Unknown")
    key = name.replace("tool_", "")
    label = key.replace("_", " ").title()
    return (key, label)


async def get_tool_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    tool_id: UUID | None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    bypass_cache: bool = False,
) -> GetToolApiResponse:
    """Tool GET using composable infra functions.

    Flow:
      1. resolve_common_context(profile_id) → profile, tool_graph, runs
      2. resolve_tool_permissions_context → access check (404, 403, fail fast)
      3. resolve_tool_artifact_context(tool_id, draft_id, ...) → hydrated resources
      4. score_tools(tool_graph, TOOL_RESOURCES) → per-resource tool picks
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
        artifact_type="tool",
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
    if tool_id is not None:
        async with pool.acquire() as conn:
            perms = await resolve_tool_permissions_context(conn, tool_id)

        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Tool {tool_id} not found",
            )

        if not has_access(profile.role):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this tool.",
            )

    # ── Step 3: Tool artifact context ─────────────────────────────────────

    tool_ctx = await resolve_tool_artifact_context(
        pool,
        redis,
        tool_id=tool_id,
        group_id=group_id,
        draft_id=draft_id,
        bypass_cache=bypass_cache,
    )

    # ── Step 4: Tool scoring ─────────────────────────────────────────────

    scores = score_tools(common.tool_graph, TOOL_RESOURCES)

    agent_ids: dict[str, UUID | None] = {
        r: (scores.best[r].agent_id if scores.best.get(r) else None)
        for r in TOOL_RESOURCES
    }

    tool_ids_map: dict[str, UUID | None] = {
        r: (scores.best[r].tool_id if scores.best.get(r) else None)
        for r in TOOL_RESOURCES
    }

    # ── Step 5: Permissions ──────────────────────────────────────────────

    active_agent_count = perms.active_agent_count if perms else 0

    can_edit = compute_can_edit(
        user_role=profile.role,
        active_agent_count=active_agent_count,
    )

    disabled_reason = compute_disabled_reason(
        user_role=profile.role,
        active_agent_count=active_agent_count,
    )

    # ── Step 6: Show / Required / AI flags ───────────────────────────────

    names_has_tools = scores.has_any.get("names", False)

    all_args = dedupe_by_id(
        tool_ctx.resources["args"].selected + tool_ctx.resources["args"].suggestions
    )
    all_arg_positions = dedupe_by_id(
        tool_ctx.resources["arg_positions"].selected
        + tool_ctx.resources["arg_positions"].suggestions
    )
    all_args_outputs = dedupe_by_id(
        tool_ctx.resources["args_outputs"].selected
        + tool_ctx.resources["args_outputs"].suggestions
    )
    all_artifacts = dedupe_by_id(
        tool_ctx.resources["artifacts"].selected
        + tool_ctx.resources["artifacts"].suggestions
    )
    all_operations = dedupe_by_id(
        tool_ctx.resources["operations"].selected
        + tool_ctx.resources["operations"].suggestions
    )

    show_flags_map = {
        "names": compute_show_name(names_has_tools),
        "descriptions": compute_show_description(),
        "flags": compute_show_flag(),
        "args": compute_show_args(len(all_args)),
        "arg_positions": compute_show_arg_positions(
            len(all_arg_positions), len(all_args)
        ),
        "args_outputs": compute_show_args_outputs(len(all_args_outputs)),
        "artifacts": compute_show_artifacts(len(all_artifacts)),
        "operations": compute_show_operations(len(all_operations)),
    }

    required_flags_map = {
        "names": compute_name_required(),
        "descriptions": compute_description_required(),
        "flags": compute_flag_required(),
        "args": compute_args_required(),
        "arg_positions": False,
        "args_outputs": compute_args_outputs_required(),
        "artifacts": compute_artifacts_required(),
        "operations": compute_operations_required(),
    }

    def compute_show_ai_generate(resource: str) -> bool:
        return agent_ids.get(resource) is not None

    show_ai_generate_map = {r: compute_show_ai_generate(r) for r in TOOL_RESOURCES}

    basic_show_ai_generate = any(
        show_ai_generate_map.get(r, False) for r in ("names", "descriptions", "flags")
    )

    # ── Step 7: Response assembly ────────────────────────────────────────

    # Flags — enriched format
    all_flags = dedupe_by_id(
        tool_ctx.resources["flags"].selected + tool_ctx.resources["flags"].suggestions
    )
    tool_flags = [
        ToolFlagConfig(
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
    if tool_ctx.resources["flags"].selected:
        f = tool_ctx.resources["flags"].selected[0]
        if f.id:
            current_flag = ToolFlagConfig(
                key=derive_flag_key_and_label(f.name)[0],
                label=derive_flag_key_and_label(f.name)[1],
                description=f.description,
                icon_id=f.icon,
                flag_option_id=f.id,
                show=show_flags_map.get("flags", True),
                required=required_flags_map.get("flags", False),
                generated=f.generated,
            )

    # Names, Descriptions — all = selected + suggestions deduped
    all_names = dedupe_by_id(
        tool_ctx.resources["names"].selected + tool_ctx.resources["names"].suggestions
    )
    all_descriptions = dedupe_by_id(
        tool_ctx.resources["descriptions"].selected
        + tool_ctx.resources["descriptions"].suggestions
    )

    # Sort args by arg_position value
    arg_position_value_by_args_id: dict[Any, int] = {
        ap.args_id: ap.value for ap in all_arg_positions if ap.args_id is not None
    }

    def _args_sort_key(arg: Any) -> tuple[int, str]:
        if arg.id in arg_position_value_by_args_id:
            return (arg_position_value_by_args_id[arg.id], arg.name or "")
        return (10_000, arg.name or "")

    all_args = sorted(all_args, key=_args_sort_key)

    # Current selections
    selected_args_ids = {a.id for a in tool_ctx.resources["args"].selected}
    args_current = sorted(
        [a for a in all_args if a.id in selected_args_ids],
        key=_args_sort_key,
    )
    arg_positions_current = tool_ctx.resources["arg_positions"].selected
    args_outputs_current = tool_ctx.resources["args_outputs"].selected

    # Suggestions maps (IDs only)
    suggestions_map = {
        "names": [n.id for n in tool_ctx.resources["names"].suggestions],
        "descriptions": [d.id for d in tool_ctx.resources["descriptions"].suggestions],
        "args": [a.id for a in tool_ctx.resources["args"].suggestions],
        "arg_positions": [
            ap.id for ap in tool_ctx.resources["arg_positions"].suggestions
        ],
        "args_outputs": [
            ao.id for ao in tool_ctx.resources["args_outputs"].suggestions
        ],
        "artifacts": [a.id for a in tool_ctx.resources["artifacts"].suggestions],
        "operations": [o.id for o in tool_ctx.resources["operations"].suggestions],
    }

    def _section(resource_key: str) -> dict:
        return {
            "show": show_flags_map.get(resource_key, False),
            "required": required_flags_map.get(resource_key, False),
            "suggestions": suggestions_map.get(resource_key, []),
            "show_ai_generate": show_ai_generate_map.get(resource_key, False),
            "tool_id": tool_ids_map.get(resource_key),
        }

    return GetToolApiResponse(
        actor_name=profile.name,
        tool_exists=tool_ctx.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        draft_version=tool_ctx.draft_version,
        group_id=group_id,
        basic_show_ai_generate=basic_show_ai_generate,
        args_show_ai_generate=show_ai_generate_map.get("args", False),
        arg_positions_show_ai_generate=show_ai_generate_map.get("arg_positions", False),
        args_outputs_show_ai_generate=show_ai_generate_map.get("args_outputs", False),
        names=ToolNameSection(
            **_section("names"),
            resource=tool_ctx.resources["names"].selected[0]
            if tool_ctx.resources["names"].selected
            else None,
            resources=all_names,
        ),
        descriptions=ToolDescriptionSection(
            **_section("descriptions"),
            resource=tool_ctx.resources["descriptions"].selected[0]
            if tool_ctx.resources["descriptions"].selected
            else None,
            resources=all_descriptions,
        ),
        flags=ToolFlagSection(
            **_section("flags"),
            current=current_flag,
            resources=tool_flags,
        ),
        args=ToolArgSection(
            **_section("args"),
            current=args_current or None,
            resources=all_args,
        ),
        arg_positions=ToolArgPositionSection(
            **_section("arg_positions"),
            current=arg_positions_current or None,
            resources=all_arg_positions,
        ),
        args_outputs=ToolArgOutputSection(
            **_section("args_outputs"),
            current=args_outputs_current or None,
            resources=all_args_outputs,
        ),
        artifacts=ToolArtifactSection(
            **_section("artifacts"),
            current=tool_ctx.resources["artifacts"].selected or None,
            resources=all_artifacts,
        ),
        operations=ToolOperationSection(
            **_section("operations"),
            current=tool_ctx.resources["operations"].selected or None,
            resources=all_operations,
        ),
    )
