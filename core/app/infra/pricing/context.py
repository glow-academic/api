"""Resolve pricing context — raw MV reads + hydrated resources.

Pricing is a dashboard endpoint with no artifact table and no drafts.
Two context resolvers:
  - resolve_pricing_context: top chart (daily cost aggregation + filter options)
  - resolve_pricing_search_context: bottom table (group list, paginated)

Both pull from runs_mv + groups_mv. Cost computation uses pricing_resource.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.types import ArtifactContext, ResourcePair

# Entry fetchers (raw MV reads)
from app.tools.entries.groups.search import search_groups
from app.tools.entries.runs.search import search_runs

# Resource get fetchers
from app.tools.resources.agents.get import get_agents
from app.tools.resources.models.get import get_models
from app.tools.resources.names.get import get_names
from app.tools.resources.pricing.get import get_pricing


async def resolve_pricing_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve pricing context for top chart (daily cost aggregation).

    Entries (raw MVs):
      - runs: runs_mv rows (all for date range, with inline pricing)

    Resources (hydrated from IDs derived from runs):
      - agents, models, pricing (for cost computation + filter options)
    """

    # Step 1: Fetch all runs for date range
    async with pool.acquire() as conn:
        all_runs, _total_count = await search_runs(
            conn,
            date_from=date_from,
            date_to=date_to,
            limit=100000,
        )

    # Step 2: Collect resource IDs
    agent_ids_set: set[UUID] = set()
    model_ids_set: set[UUID] = set()
    pricing_ids_set: set[UUID] = set()

    for run in all_runs:
        if run.agent_ids:
            agent_ids_set.update(run.agent_ids)
        if run.model_ids:
            model_ids_set.update(run.model_ids)
        for p in run.pricing:
            if p.pricing_id:
                pricing_ids_set.add(p.pricing_id)

    # Step 3: Parallel hydrate resources
    async def _get_agents() -> list:
        if not agent_ids_set:
            return []
        async with pool.acquire() as conn:
            return await get_agents(conn, list(agent_ids_set), redis, bypass_cache)

    async def _get_models() -> list:
        if not model_ids_set:
            return []
        async with pool.acquire() as conn:
            return await get_models(conn, list(model_ids_set), redis, bypass_cache)

    async def _get_pricing() -> list:
        if not pricing_ids_set:
            return []
        async with pool.acquire() as conn:
            return await get_pricing(conn, list(pricing_ids_set), redis, bypass_cache)

    agents_selected, models_selected, pricing_selected = await asyncio.gather(
        _get_agents(),
        _get_models(),
        _get_pricing(),
    )

    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=None,  # type: ignore[arg-type]
        draft_version=None,
        resources={
            "agents": ResourcePair(selected=agents_selected, suggestions=[]),
            "models": ResourcePair(selected=models_selected, suggestions=[]),
            "pricing": ResourcePair(selected=pricing_selected, suggestions=[]),
        },
        entries={
            "runs": all_runs,
        },
    )


async def resolve_pricing_search_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    session_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_order: str = "desc",
    page: int = 0,
    page_size: int = 50,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve pricing search context for bottom table (group list).

    Entries (raw MVs):
      - groups: groups_mv rows (paginated)
      - total_groups: groups_mv rows (all matching, for total_count)
      - runs: runs_mv rows (for groups on current page)

    Resources (hydrated from IDs derived from runs):
      - agents, models, names, pricing (for cost computation + display)
    """
    page_offset = page * page_size

    # Step 1: Paginated groups + total count
    async def _fetch_groups_page() -> list:
        async with pool.acquire() as conn:
            return await search_groups(
                conn,
                session_ids=session_ids,
                date_from=date_from,
                date_to=date_to,
                limit=page_size,
                offset=page_offset,
            )

    async def _fetch_groups_total() -> list:
        async with pool.acquire() as conn:
            return await search_groups(
                conn,
                session_ids=session_ids,
                date_from=date_from,
                date_to=date_to,
                limit=100000,
                offset=0,
            )

    all_groups, total_groups = await asyncio.gather(
        _fetch_groups_page(),
        _fetch_groups_total(),
    )

    # Step 2: Fetch runs for groups on current page
    group_ids = [g.id for g in all_groups]
    if group_ids:
        async with pool.acquire() as conn:
            all_runs = (await search_runs(conn, group_ids=group_ids, limit=100000))[0]
    else:
        all_runs = []

    # Step 3: Collect resource IDs
    agent_ids_set: set[UUID] = set()
    model_ids_set: set[UUID] = set()
    pricing_ids_set: set[UUID] = set()

    for run in all_runs:
        if run.agent_ids:
            agent_ids_set.update(run.agent_ids)
        if run.model_ids:
            model_ids_set.update(run.model_ids)
        for p in run.pricing:
            if p.pricing_id:
                pricing_ids_set.add(p.pricing_id)

    # Names for display (agents + models)
    all_name_ids = list(agent_ids_set | model_ids_set)

    # Step 4: Parallel hydrate resources
    async def _get_agents() -> list:
        if not agent_ids_set:
            return []
        async with pool.acquire() as conn:
            return await get_agents(conn, list(agent_ids_set), redis, bypass_cache)

    async def _get_models() -> list:
        if not model_ids_set:
            return []
        async with pool.acquire() as conn:
            return await get_models(conn, list(model_ids_set), redis, bypass_cache)

    async def _get_pricing() -> list:
        if not pricing_ids_set:
            return []
        async with pool.acquire() as conn:
            return await get_pricing(conn, list(pricing_ids_set), redis, bypass_cache)

    async def _get_names() -> list:
        if not all_name_ids:
            return []
        async with pool.acquire() as conn:
            return await get_names(conn, all_name_ids, redis, bypass_cache=bypass_cache)

    (
        agents_selected,
        models_selected,
        pricing_selected,
        names_selected,
    ) = await asyncio.gather(
        _get_agents(),
        _get_models(),
        _get_pricing(),
        _get_names(),
    )

    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=None,  # type: ignore[arg-type]
        draft_version=None,
        resources={
            "agents": ResourcePair(selected=agents_selected, suggestions=[]),
            "models": ResourcePair(selected=models_selected, suggestions=[]),
            "pricing": ResourcePair(selected=pricing_selected, suggestions=[]),
            "names": ResourcePair(selected=names_selected, suggestions=[]),
        },
        entries={
            "groups": all_groups,
            "total_groups": total_groups,
            "runs": all_runs,
        },
    )
