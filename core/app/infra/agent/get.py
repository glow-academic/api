"""Canonical shared agent GET operation."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.agent.context import resolve_agent_context
from app.infra.agent.permissions import (
    AGENT_BASIC_RESOURCES,
    AGENT_GENERAL_RESOURCES,
    AGENT_RESOURCES,
    compute_can_edit,
    compute_disabled_reason,
    get_missing_tools,
    has_access,
)
from app.infra.agent.permissions_context import resolve_agent_permissions_context
from app.infra.agent.types import (
    AgentDepartmentResource,
    AgentDescriptionResource,
    AgentFlagConfig,
    AgentInstructionResource,
    AgentModelResource,
    AgentNameResource,
    AgentPromptResource,
    AgentQualityResource,
    AgentReasoningLevelResource,
    AgentRubricResource,
    AgentTemperatureLevelResource,
    AgentToolResource,
    AgentVoiceResource,
    GetAgentApiResponse,
    SectionFilter,
)
from app.infra.common_context import resolve_common_context
from app.infra.helpers import sorted_dedupe_by_id
from app.infra.tool_graph import score_tools

SECTIONS = [
    "names",
    "descriptions",
    "models",
    "prompts",
    "instructions",
    "flags",
    "departments",
    "tools",
    "temperature_levels",
    "reasoning_levels",
    "voices",
    "qualities",
    "rubrics",
]


def derive_flag_key_and_label(name: str | None) -> tuple[str, str]:
    """Derive a flag key/label from names like 'agent_active'."""
    if not name:
        return ("unknown", "Unknown")
    key = name.replace("agent_", "")
    label = key.replace("_", " ").title()
    return (key, label)


def _sf(filters: dict[str, SectionFilter | None], section: str, attr: str, default=None):
    section_filter = filters.get(section)
    if section_filter is None:
        return default
    return getattr(section_filter, attr, default)


def _filter_items(items: list | None, section: str, *, selected_only: dict[str, bool], suggested_only: dict[str, bool]):
    if items is None:
        return None
    result = items
    if selected_only.get(section):
        result = [item for item in result if getattr(item, "selected", False)]
    if suggested_only.get(section):
        result = [item for item in result if getattr(item, "suggested", False)]
    return result


def _decorate(items: list, selected_items: list, suggestions: list, pending_ids: set[UUID]) -> list[dict]:
    selected_ids = {getattr(item, "id", None) for item in selected_items}
    suggestion_ids = {getattr(item, "id", None) for item in suggestions}
    result: list[dict] = []
    for item in items:
        item_id = getattr(item, "id", None)
        payload = item.model_dump(mode="json")
        payload.update(
            suggested=item_id in suggestion_ids,
            selected=item_id in selected_ids,
            pending=item_id in pending_ids,
        )
        result.append(payload)
    return result


async def get_agent_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    id: UUID | None = None,
    agent_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    filters: dict[str, SectionFilter | None] | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> GetAgentApiResponse:
    """Resolve the canonical agent artifact bundle for any surface."""

    resolved_filters = dict(filters or {})
    agent_id = id or agent_id

    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        draft_id=draft_id,
        artifact_type="agent",
        bypass_cache=bypass_cache,
    )
    if common is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    actor = common.profile
    effective_group_id = group_id or actor.group_id

    perms = None
    if agent_id is not None:
        async with pool.acquire() as conn:
            perms = await resolve_agent_permissions_context(conn, agent_id)
        if not perms.exists:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
        if not has_access(actor.role_level, actor.department_ids, perms.department_ids):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this agent. It may be restricted to other departments.",
            )

    agent_ctx = await resolve_agent_context(
        pool,
        redis,
        agent_id=agent_id,
        group_id=effective_group_id,
        draft_id=draft_id,
        user_department_ids=actor.department_ids,
        names_search=_sf(resolved_filters, "names", "search"),
        descriptions_search=_sf(resolved_filters, "descriptions", "search"),
        models_search=_sf(resolved_filters, "models", "search"),
        prompts_search=_sf(resolved_filters, "prompts", "search"),
        instructions_search=_sf(resolved_filters, "instructions", "search"),
        flags_search=_sf(resolved_filters, "flags", "search"),
        departments_search=_sf(resolved_filters, "departments", "search"),
        tools_search=_sf(resolved_filters, "tools", "search"),
        temperature_levels_search=_sf(resolved_filters, "temperature_levels", "search"),
        reasoning_levels_search=_sf(resolved_filters, "reasoning_levels", "search"),
        voices_search=_sf(resolved_filters, "voices", "search"),
        qualities_search=_sf(resolved_filters, "qualities", "search"),
        rubrics_search=_sf(resolved_filters, "rubrics", "search"),
        names_limit=_sf(resolved_filters, "names", "limit"),
        descriptions_limit=_sf(resolved_filters, "descriptions", "limit"),
        models_limit=_sf(resolved_filters, "models", "limit"),
        prompts_limit=_sf(resolved_filters, "prompts", "limit"),
        instructions_limit=_sf(resolved_filters, "instructions", "limit"),
        flags_limit=_sf(resolved_filters, "flags", "limit"),
        departments_limit=_sf(resolved_filters, "departments", "limit"),
        tools_limit=_sf(resolved_filters, "tools", "limit"),
        temperature_levels_limit=_sf(resolved_filters, "temperature_levels", "limit"),
        reasoning_levels_limit=_sf(resolved_filters, "reasoning_levels", "limit"),
        voices_limit=_sf(resolved_filters, "voices", "limit"),
        qualities_limit=_sf(resolved_filters, "qualities", "limit"),
        rubrics_limit=_sf(resolved_filters, "rubrics", "limit"),
        names_selected_only=_sf(resolved_filters, "names", "selected"),
        descriptions_selected_only=_sf(resolved_filters, "descriptions", "selected"),
        models_selected_only=_sf(resolved_filters, "models", "selected"),
        prompts_selected_only=_sf(resolved_filters, "prompts", "selected"),
        instructions_selected_only=_sf(resolved_filters, "instructions", "selected"),
        flags_selected_only=_sf(resolved_filters, "flags", "selected"),
        departments_selected_only=_sf(resolved_filters, "departments", "selected"),
        tools_selected_only=_sf(resolved_filters, "tools", "selected"),
        temperature_levels_selected_only=_sf(resolved_filters, "temperature_levels", "selected"),
        reasoning_levels_selected_only=_sf(resolved_filters, "reasoning_levels", "selected"),
        voices_selected_only=_sf(resolved_filters, "voices", "selected"),
        qualities_selected_only=_sf(resolved_filters, "qualities", "selected"),
        rubrics_selected_only=_sf(resolved_filters, "rubrics", "selected"),
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, AGENT_RESOURCES)
    include = {section: _sf(resolved_filters, section, "include") is not False for section in SECTIONS}
    selected_only = {section: bool(_sf(resolved_filters, section, "selected")) for section in SECTIONS}
    suggested_only = {section: bool(_sf(resolved_filters, section, "suggested")) for section in SECTIONS}

    has_agent_access = has_access(
        actor.role_level,
        actor.department_ids,
        perms.department_ids if perms else [],
    )
    missing_tools = get_missing_tools(
        names_has_tools=scores.has_any.get("names", False),
        models_has_tools=scores.has_any.get("models", False),
        prompts_has_tools=scores.has_any.get("prompts", False),
        instructions_has_tools=scores.has_any.get("instructions", False),
    )
    can_edit = compute_can_edit(
        role_level=actor.role_level,
        role_permissions=actor.role_permissions,
        has_agent_access=has_agent_access,
        missing_tools=missing_tools,
        agent_id=agent_id,
    )
    disabled_reason = compute_disabled_reason(
        role_level=actor.role_level,
        role_permissions=actor.role_permissions,
        has_agent_access=has_agent_access,
        missing_tools=missing_tools,
        agent_id=agent_id,
    )

    pending_ids = set(agent_ctx.entries.get("pending_ids", set()))

    names_items = sorted_dedupe_by_id(agent_ctx.resources["names"].suggestions + agent_ctx.resources["names"].selected)
    descriptions_items = sorted_dedupe_by_id(agent_ctx.resources["descriptions"].suggestions + agent_ctx.resources["descriptions"].selected)
    models_items = sorted_dedupe_by_id(agent_ctx.resources["models"].suggestions + agent_ctx.resources["models"].selected)
    prompts_items = sorted_dedupe_by_id(agent_ctx.resources["prompts"].suggestions + agent_ctx.resources["prompts"].selected)
    instructions_items = sorted_dedupe_by_id(agent_ctx.resources["instructions"].suggestions + agent_ctx.resources["instructions"].selected)
    departments_items = sorted_dedupe_by_id(agent_ctx.resources["departments"].suggestions + agent_ctx.resources["departments"].selected)
    tools_items = sorted_dedupe_by_id(agent_ctx.resources["tools"].suggestions + agent_ctx.resources["tools"].selected)
    temperature_levels_items = sorted_dedupe_by_id(agent_ctx.resources["temperature_levels"].suggestions + agent_ctx.resources["temperature_levels"].selected)
    reasoning_levels_items = sorted_dedupe_by_id(agent_ctx.resources["reasoning_levels"].suggestions + agent_ctx.resources["reasoning_levels"].selected)
    voices_items = sorted_dedupe_by_id(agent_ctx.resources["voices"].suggestions + agent_ctx.resources["voices"].selected)
    qualities_items = sorted_dedupe_by_id(agent_ctx.resources["qualities"].suggestions + agent_ctx.resources["qualities"].selected)
    rubrics_items = sorted_dedupe_by_id(agent_ctx.resources["rubrics"].suggestions + agent_ctx.resources["rubrics"].selected)

    raw_flags = sorted_dedupe_by_id(agent_ctx.resources["flags"].suggestions + agent_ctx.resources["flags"].selected)
    selected_flag_ids = {getattr(item, "id", None) for item in agent_ctx.resources["flags"].selected}
    suggestion_flag_ids = {getattr(item, "id", None) for item in agent_ctx.resources["flags"].suggestions}
    flags_items = [
        AgentFlagConfig(
            key=derive_flag_key_and_label(getattr(flag, "name", None) or getattr(flag, "type", None))[0],
            label=derive_flag_key_and_label(getattr(flag, "name", None) or getattr(flag, "type", None))[1],
            description=getattr(flag, "description", None),
            icon_id=getattr(flag, "icon_id", None),
            flag_option_id=getattr(flag, "id", None),
            generated=getattr(flag, "generated", None),
            suggested=getattr(flag, "id", None) in suggestion_flag_ids,
            selected=getattr(flag, "id", None) in selected_flag_ids,
            pending=getattr(flag, "id", None) in pending_ids,
        )
        for flag in raw_flags
        if getattr(flag, "id", None) is not None
    ]

    response = GetAgentApiResponse(
        actor_name=actor.name,
        agent_exists=agent_ctx.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        group_id=effective_group_id,
        agent_id=agent_ctx.artifact_id,
        show_ai_generate=any(scores.has_any.get(resource, False) for resource in AGENT_GENERAL_RESOURCES),
        basic_show_ai_generate=any(scores.has_any.get(resource, False) for resource in AGENT_BASIC_RESOURCES),
        general_show_ai_generate=any(scores.has_any.get(resource, False) for resource in AGENT_GENERAL_RESOURCES),
        pending_ids=sorted(pending_ids) or None,
        names=_filter_items(
            [AgentNameResource(**item) for item in _decorate(names_items, agent_ctx.resources["names"].selected, agent_ctx.resources["names"].suggestions, pending_ids)],
            "names",
            selected_only=selected_only,
            suggested_only=suggested_only,
        ) if include["names"] else None,
        descriptions=_filter_items(
            [AgentDescriptionResource(**item) for item in _decorate(descriptions_items, agent_ctx.resources["descriptions"].selected, agent_ctx.resources["descriptions"].suggestions, pending_ids)],
            "descriptions",
            selected_only=selected_only,
            suggested_only=suggested_only,
        ) if include["descriptions"] else None,
        models=_filter_items(
            [AgentModelResource(**item) for item in _decorate(models_items, agent_ctx.resources["models"].selected, agent_ctx.resources["models"].suggestions, pending_ids)],
            "models",
            selected_only=selected_only,
            suggested_only=suggested_only,
        ) if include["models"] else None,
        prompts=_filter_items(
            [AgentPromptResource(**item) for item in _decorate(prompts_items, agent_ctx.resources["prompts"].selected, agent_ctx.resources["prompts"].suggestions, pending_ids)],
            "prompts",
            selected_only=selected_only,
            suggested_only=suggested_only,
        ) if include["prompts"] else None,
        instructions=_filter_items(
            [AgentInstructionResource(**item) for item in _decorate(instructions_items, agent_ctx.resources["instructions"].selected, agent_ctx.resources["instructions"].suggestions, pending_ids)],
            "instructions",
            selected_only=selected_only,
            suggested_only=suggested_only,
        ) if include["instructions"] else None,
        flags=_filter_items(
            flags_items,
            "flags",
            selected_only=selected_only,
            suggested_only=suggested_only,
        ) if include["flags"] else None,
        departments=_filter_items(
            [
                AgentDepartmentResource(
                    department_id=getattr(item, "id", None),
                    name=getattr(item, "name", None),
                    description=getattr(item, "description", None),
                    generated=getattr(item, "generated", None),
                    suggested=getattr(item, "id", None) in {getattr(s, "id", None) for s in agent_ctx.resources["departments"].suggestions},
                    selected=getattr(item, "id", None) in {getattr(s, "id", None) for s in agent_ctx.resources["departments"].selected},
                    pending=getattr(item, "id", None) in pending_ids,
                )
                for item in departments_items
            ],
            "departments",
            selected_only=selected_only,
            suggested_only=suggested_only,
        ) if include["departments"] else None,
        tools=_filter_items(
            [AgentToolResource(**item) for item in _decorate(tools_items, agent_ctx.resources["tools"].selected, agent_ctx.resources["tools"].suggestions, pending_ids)],
            "tools",
            selected_only=selected_only,
            suggested_only=suggested_only,
        ) if include["tools"] else None,
        temperature_levels=_filter_items(
            [AgentTemperatureLevelResource(**item) for item in _decorate(temperature_levels_items, agent_ctx.resources["temperature_levels"].selected, agent_ctx.resources["temperature_levels"].suggestions, pending_ids)],
            "temperature_levels",
            selected_only=selected_only,
            suggested_only=suggested_only,
        ) if include["temperature_levels"] else None,
        reasoning_levels=_filter_items(
            [AgentReasoningLevelResource(**item) for item in _decorate(reasoning_levels_items, agent_ctx.resources["reasoning_levels"].selected, agent_ctx.resources["reasoning_levels"].suggestions, pending_ids)],
            "reasoning_levels",
            selected_only=selected_only,
            suggested_only=suggested_only,
        ) if include["reasoning_levels"] else None,
        voices=_filter_items(
            [AgentVoiceResource(**item) for item in _decorate(voices_items, agent_ctx.resources["voices"].selected, agent_ctx.resources["voices"].suggestions, pending_ids)],
            "voices",
            selected_only=selected_only,
            suggested_only=suggested_only,
        ) if include["voices"] else None,
        qualities=_filter_items(
            [AgentQualityResource(**item) for item in _decorate(qualities_items, agent_ctx.resources["qualities"].selected, agent_ctx.resources["qualities"].suggestions, pending_ids)],
            "qualities",
            selected_only=selected_only,
            suggested_only=suggested_only,
        ) if include["qualities"] else None,
        rubrics=_filter_items(
            [AgentRubricResource(**item) for item in _decorate(rubrics_items, agent_ctx.resources["rubrics"].selected, agent_ctx.resources["rubrics"].suggestions, pending_ids)],
            "rubrics",
            selected_only=selected_only,
            suggested_only=suggested_only,
        ) if include["rubrics"] else None,
    )
    return response
