"""Canonical shared group GET operation."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from uuid import UUID

import asyncpg
from fastapi import HTTPException

from app.infra.common_context import resolve_common_context
from app.infra.group.context import resolve_group_context
from app.infra.pricing import compute_costs_from_runs
from app.infra.tool_graph import score_tools
from app.infra.group.types import (
    GetGroupDetailResponse,
    GroupDetailCallItem,
    GroupDetailMessageItem,
    GroupDetailResourceItem,
    GroupDetailRunItem,
    GroupDetailRunWithMessages,
    GroupInternalData,
)
from app.tools.resources.agents.get import get_agents
from app.tools.resources.models.get import get_models
from app.tools.resources.providers.get import get_providers
from app.tools.resources.systems.get import get_systems
from app.tools.resources.tools.get import get_tools

GROUP_BUNDLE_ENTRIES: set[str] = {"problems"}


async def get_group_internal(
    pool: asyncpg.Pool,
    profile_id: UUID,
    group_id: UUID,
    *,
    redis,
    bypass_cache: bool = False,
    message_limit: int | None = None,
    message_offset: int | None = None,
) -> GroupInternalData:
    """Resolve raw group detail data before HTTP shaping."""

    async def _resolve_group() -> object:
        return await resolve_group_context(
            pool,
            redis,
            group_id=group_id,
            profile_id=profile_id,
            bypass_cache=bypass_cache,
            message_limit=message_limit,
            message_offset=message_offset,
        )

    async def _resolve_common() -> object:
        return await resolve_common_context(
            pool,
            redis,
            profile_id=profile_id,
            bypass_cache=bypass_cache,
        )

    ctx, common = await asyncio.gather(_resolve_group(), _resolve_common())

    runs = ctx.entries.get("runs", [])
    messages = ctx.entries.get("messages", [])
    calls = ctx.entries.get("calls", [])
    actor_name_items = ctx.entries.get("actor_name_items", [])
    actor_name = actor_name_items[0].name if actor_name_items else None
    group_name = ctx.entries.get("group_name")
    total_message_count = ctx.entries.get("total_message_count", 0)

    if not runs:
        return GroupInternalData(
            group_exists=False,
            actor_name=actor_name,
            group_id=group_id,
        )

    names_rp = ctx.resources.get("names")
    names_list = names_rp.selected if names_rp else []
    tools_rp = ctx.resources.get("tools")
    tools_list = tools_rp.selected if tools_rp else []

    config_agents: list = []
    config_models: list = []
    config_providers: list = []
    config_tools: list = []
    config_systems: list = []
    config_profile: list = []
    runs_today = None
    resource_agent_ids: dict[str, UUID | None] = {}
    resource_system_ids: dict[str, UUID | None] = {}

    if common:
        scores = score_tools(common.tool_graph, GROUP_BUNDLE_ENTRIES)
        resource_agent_ids = {
            target: (tool.agent_id if tool else None)
            for target, tool in scores.best.items()
        }
        resource_system_ids = {
            target: (tool.system_id if tool else None)
            for target, tool in scores.best.items()
        }

        all_system_ids = list(
            dict.fromkeys(tool.system_id for tool in common.tool_graph.tools)
        )
        all_agent_ids = list(
            dict.fromkeys(tool.agent_id for tool in common.tool_graph.tools)
        )
        all_tool_ids = list(
            dict.fromkeys(tool.tool_id for tool in common.tool_graph.tools)
        )

        async def _fetch_systems() -> list:
            if not all_system_ids:
                return []
            async with pool.acquire() as conn:
                return await get_systems(conn, all_system_ids, redis, bypass_cache)

        async def _fetch_agents() -> list:
            if not all_agent_ids:
                return []
            async with pool.acquire() as conn:
                return await get_agents(conn, all_agent_ids, redis, bypass_cache)

        async def _fetch_tools_config() -> list:
            if not all_tool_ids:
                return []
            async with pool.acquire() as conn:
                return await get_tools(conn, all_tool_ids, redis, bypass_cache)

        config_systems, config_agents, config_tools = await asyncio.gather(
            _fetch_systems(),
            _fetch_agents(),
            _fetch_tools_config(),
        )

        model_ids = list(
            dict.fromkeys(agent.model_id for agent in config_agents if agent.model_id)
        )
        if model_ids:
            async with pool.acquire() as conn:
                config_models = await get_models(conn, model_ids, redis, bypass_cache)

        provider_ids = list(
            dict.fromkeys(
                model.provider_id for model in config_models if model.provider_id
            )
        )
        if provider_ids:
            async with pool.acquire() as conn:
                config_providers = await get_providers(
                    conn, provider_ids, redis, bypass_cache
                )

        if common.profile:
            from app.tools.resources.profiles.get import get_profiles

            async with pool.acquire() as conn:
                config_profile = await get_profiles(
                    conn,
                    [common.profile.profiles_id],
                    redis,
                    bypass_cache,
                )

        runs_today = common.runs if common.runs else None

    return GroupInternalData(
        group_exists=True,
        runs=runs,
        messages=messages,
        calls=calls,
        config_agents=config_agents,
        config_models=config_models,
        config_providers=config_providers,
        config_tools=config_tools,
        config_systems=config_systems,
        config_profile=config_profile,
        runs_today=runs_today,
        resource_agent_ids=resource_agent_ids,
        resource_system_ids=resource_system_ids,
        group_id=group_id,
        actor_name=actor_name,
        group_name=group_name,
        total_message_count=total_message_count,
        name_map={item.id: item.name for item in names_list if item.id and item.name},
        tool_name_map={
            item.id: item.name for item in tools_list if item.id and item.name
        },
    )


async def get_group_impl(
    pool: asyncpg.Pool,
    *,
    profile_id: UUID,
    group_id: UUID,
    redis,
    bypass_cache: bool = False,
    message_limit: int | None = None,
    message_offset: int | None = None,
) -> GetGroupDetailResponse:
    """Resolve the canonical group detail response for any surface."""
    data = await get_group_internal(
        pool=pool,
        profile_id=profile_id,
        group_id=group_id,
        redis=redis,
        bypass_cache=bypass_cache,
        message_limit=message_limit,
        message_offset=message_offset,
    )

    if not data.group_exists:
        raise HTTPException(status_code=404, detail=f"Group not found: {group_id}")
    if not data.runs:
        raise HTTPException(
            status_code=403,
            detail="You don't have access to this group. It may be restricted to other departments.",
        )

    async with pool.acquire() as conn:
        run_costs = await compute_costs_from_runs(conn, data.runs, bypass_cache)

    run_messages: dict[UUID, list] = defaultdict(list)
    for message in data.messages:
        if message.run_id:
            run_messages[message.run_id].append(message)

    calls_by_run: dict[UUID, list] = defaultdict(list)
    for call in data.calls:
        if call.run_id:
            calls_by_run[call.run_id].append(call)

    all_model_ids: set[UUID] = set()
    all_agent_ids: set[UUID] = set()
    all_profile_ids: set[UUID] = set()
    for run in data.runs:
        if run.model_ids:
            all_model_ids.update(run.model_ids)
        if run.agent_ids:
            all_agent_ids.update(run.agent_ids)

    runs: list[GroupDetailRunWithMessages] = []
    for run in data.runs:
        run_id = run.run_id
        agent_id = run.agent_ids[0] if run.agent_ids else None
        model_id = run.model_ids[0] if run.model_ids else None
        run_item = GroupDetailRunItem(
            id=run_id,
            created_at=run.run_created_at,
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            cached_input_tokens=run.cached_input_tokens,
            cost=float(run_costs.get(run_id, 0)),
            model_id=model_id,
            agent_id=agent_id,
            profile_id=None,
        )

        messages: list[GroupDetailMessageItem] = []
        for message in run_messages.get(run_id, []):
            messages.append(
                GroupDetailMessageItem(
                    id=message.message_id,
                    role=message.role,
                    text_upload_ids=list(message.text_upload_ids or []),
                    audio_upload_ids=list(message.audio_upload_ids or []),
                    image_upload_ids=list(message.image_upload_ids or []),
                    video_upload_ids=list(message.video_upload_ids or []),
                    file_upload_ids=list(message.file_upload_ids or []),
                    call_upload_ids=list(message.call_upload_ids or []),
                )
            )

        run_calls = calls_by_run.get(run_id, [])
        if run_calls and messages:
            for call in run_calls:
                messages[-1].calls.append(
                    GroupDetailCallItem(
                        id=call.call_id,
                        template_name=data.tool_name_map.get(call.tool_id)
                        if call.tool_id
                        else None,
                        file_path=call.file_path,
                        created_at=call.call_created_at,
                    )
                )

        runs.append(
            GroupDetailRunWithMessages(
                run=run_item,
                messages=messages,
                previous_context_start_index=None,
            )
        )

    models_list = [
        GroupDetailResourceItem(model_id=model_id, name=data.name_map.get(model_id))
        for model_id in all_model_ids
    ]
    agents_list = [
        GroupDetailResourceItem(agent_id=agent_id, name=data.name_map.get(agent_id))
        for agent_id in all_agent_ids
    ]
    profiles_list = [
        GroupDetailResourceItem(
            profile_id=profile_id_item, name=data.name_map.get(profile_id_item)
        )
        for profile_id_item in all_profile_ids
    ]

    return GetGroupDetailResponse(
        group_exists=True,
        actor_name=data.actor_name,
        group_name=data.group_name,
        total_message_count=data.total_message_count,
        runs=runs,
        models=models_list,
        agents=agents_list,
        profiles=profiles_list,
    )
