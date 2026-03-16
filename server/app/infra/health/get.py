"""Canonical shared health GET operation."""

from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import UUID

import asyncpg

from app.infra.analytics_facets import (
    HIDDEN,
    VISIBLE,
    AnalyticsFacetsConfig,
    resolve_analytics_facets,
)
from app.infra.common_context import resolve_common_context
from app.infra.health.context import resolve_health_context
from app.infra.tool_graph import score_tools
from app.infra.auth.types import AnalyticsFacets, AnalyticsFilterFields
from app.infra.health.types import (
    HealthInternalData,
    HealthResponse,
    HealthViews,
)
from app.tools.resources.agents.get import get_agents
from app.tools.resources.models.get import get_models
from app.tools.resources.providers.get import get_providers
from app.tools.resources.systems.get import get_systems
from app.tools.resources.tools.get import get_tools

HEALTH_FACETS_CONFIG = AnalyticsFacetsConfig(
    fields=AnalyticsFilterFields(
        date_range=VISIBLE,
        departments=HIDDEN,
        cohorts=HIDDEN,
        roles=HIDDEN,
        attempts=HIDDEN,
    ),
    mv_source="health",
)

HEALTH_BUNDLE_ENTRIES: set[str] = {"problems"}


async def get_health_internal(
    pool: asyncpg.Pool,
    profile_id: UUID,
    *,
    redis,
    service: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page_limit: int = 168,
    page_offset: int = 0,
    bypass_cache: bool = False,
) -> HealthInternalData:
    """Resolve raw health artifact data before HTTP shaping."""

    async def _resolve_health() -> object:
        return await resolve_health_context(
            pool,
            redis,
            service=service,
            date_from=date_from,
            date_to=date_to,
            page_limit=page_limit,
            page_offset=page_offset,
            bypass_cache=bypass_cache,
        )

    async def _resolve_common() -> object:
        return await resolve_common_context(
            pool,
            redis,
            profile_id=profile_id,
            bypass_cache=bypass_cache,
        )

    ctx, common = await asyncio.gather(_resolve_health(), _resolve_common())

    health = ctx.entries.get("health", [])
    metrics = ctx.entries.get("metrics", [])

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
        scores = score_tools(common.tool_graph, HEALTH_BUNDLE_ENTRIES)
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

    return HealthInternalData(
        health=health,
        metrics=metrics,
        config_agents=config_agents,
        config_models=config_models,
        config_providers=config_providers,
        config_tools=config_tools,
        config_systems=config_systems,
        config_profile=config_profile,
        runs_today=runs_today,
        resource_agent_ids=resource_agent_ids,
        resource_system_ids=resource_system_ids,
        group_id=None,
    )


async def get_health_impl(
    pool: asyncpg.Pool,
    *,
    profile_id: UUID,
    redis,
    service: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page_limit: int = 168,
    page_offset: int = 0,
    bypass_cache: bool = False,
) -> HealthResponse:
    """Resolve the canonical health response for any surface."""
    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        bypass_cache=bypass_cache,
    )

    analytics_facets: AnalyticsFacets | None = None
    if common and common.profile:
        data, analytics_facets = await asyncio.gather(
            get_health_internal(
                pool,
                profile_id,
                redis=redis,
                service=service,
                date_from=date_from,
                date_to=date_to,
                page_limit=page_limit,
                page_offset=page_offset,
                bypass_cache=bypass_cache,
            ),
            resolve_analytics_facets(
                pool,
                redis,
                config=HEALTH_FACETS_CONFIG,
                profile=common.profile,
                bypass_cache=bypass_cache,
            ),
        )
    else:
        data = await get_health_internal(
            pool,
            profile_id,
            redis=redis,
            service=service,
            date_from=date_from,
            date_to=date_to,
            page_limit=page_limit,
            page_offset=page_offset,
            bypass_cache=bypass_cache,
        )

    views = HealthViews(
        service_hourly=data.health,
        metrics_hourly=data.metrics,
    )
    return HealthResponse(
        views=views,
        total_count=len(data.health),
        analytics=analytics_facets,
    )
