"""Resolve leaderboard context — raw MV reads + hydrated resources.

Leaderboard is an analytics endpoint with no artifact table and no drafts.
Two context resolvers:
  - resolve_leaderboard_context: top sections (header metrics + accolades)
  - resolve_leaderboard_search_context: bottom table (profile rows, paginated)

Both pull from attempt_chat_mv + attempt_message_mv. All aggregation in Python.
"""

from __future__ import annotations

import asyncio
from datetime import date
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.types import ArtifactContext, ResourcePair

# Entry fetchers (raw MV reads)
from app.tools.entries.attempt_chat.search import search_attempt_chats
from app.tools.entries.attempt_message.search import search_attempt_messages

# Resource get fetchers
from app.tools.resources.profiles.get import get_profiles
from app.tools.resources.scenarios.get import get_scenarios
from app.tools.resources.simulations.get import get_simulations


async def resolve_leaderboard_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    target_profile_id: UUID | None = None,
    cohort_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    attempt_type: str | None = None,
    is_archived: bool = False,
    date_from: date | None = None,
    date_to: date | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve leaderboard context for top sections (header metrics + accolades).

    Entries (raw MVs):
      - attempt_chats: attempt_chat_mv rows (all matching, no sim/scenario filter)
      - attempt_messages: attempt_message_mv rows (for message count + response time)

    Resources (hydrated from IDs derived from attempt_chats):
      - profiles
    """
    # Step 1: Fetch attempt_chats (no simulation/scenario filter for top sections)
    async with pool.acquire() as conn:
        all_attempt_chats, _total_count = await search_attempt_chats(
            conn,
            profile_ids=[target_profile_id] if target_profile_id else None,
            cohort_ids=cohort_ids,
            department_ids=department_ids,
            attempt_type=attempt_type,
            is_archived=is_archived,
            date_from=date_from,
            date_to=date_to,
            limit=100000,
        )

    # Step 2: Fetch attempt_messages for message stats
    chat_ids = [ac.chat_id for ac in all_attempt_chats if ac.chat_id]
    if chat_ids:
        async with pool.acquire() as conn:
            all_attempt_messages = (
                await search_attempt_messages(conn, chat_ids=chat_ids, limit=1000000)
            )[0]
    else:
        all_attempt_messages = []

    # Step 3: Derive resource IDs + hydrate
    profile_ids_set: set[UUID] = set()
    for ac in all_attempt_chats:
        if ac.profile_id:
            profile_ids_set.add(ac.profile_id)

    if profile_ids_set:
        async with pool.acquire() as conn:
            profiles_selected = await get_profiles(
                conn, list(profile_ids_set), redis, bypass_cache
            )
    else:
        profiles_selected = []

    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=None,  # type: ignore[arg-type]
        draft_version=None,
        resources={
            "profiles": ResourcePair(selected=profiles_selected, suggestions=[]),
        },
        entries={
            "attempt_chats": all_attempt_chats,
            "attempt_messages": all_attempt_messages,
        },
    )


async def resolve_leaderboard_search_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    target_profile_id: UUID | None = None,
    cohort_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    simulation_ids: list[UUID] | None = None,
    scenario_ids: list[UUID] | None = None,
    attempt_type: str | None = None,
    is_archived: bool = False,
    date_from: date | None = None,
    date_to: date | None = None,
    sort_order: str = "desc",
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve leaderboard search context for bottom table (profile rows).

    Entries (raw MVs):
      - attempt_chats: attempt_chat_mv rows (filtered by sim/scenario)
      - attempt_messages: attempt_message_mv rows (for message count + response time)

    Resources (hydrated from IDs derived from attempt_chats):
      - profiles, simulations, scenarios
    """
    # Step 1: Fetch attempt_chats with full filter set
    async with pool.acquire() as conn:
        all_attempt_chats, _total_count = await search_attempt_chats(
            conn,
            profile_ids=[target_profile_id] if target_profile_id else None,
            cohort_ids=cohort_ids,
            department_ids=department_ids,
            simulation_ids=simulation_ids,
            scenario_ids=scenario_ids,
            attempt_type=attempt_type,
            is_archived=is_archived,
            date_from=date_from,
            date_to=date_to,
            sort_order=sort_order,
            limit=100000,
        )

    # Step 2: Fetch attempt_messages for message stats
    chat_ids = [ac.chat_id for ac in all_attempt_chats if ac.chat_id]
    if chat_ids:
        async with pool.acquire() as conn:
            all_attempt_messages = (
                await search_attempt_messages(conn, chat_ids=chat_ids, limit=1000000)
            )[0]
    else:
        all_attempt_messages = []

    # Step 3: Derive resource IDs
    profile_ids_set: set[UUID] = set()
    sim_ids_set: set[UUID] = set()
    scenario_ids_set: set[UUID] = set()

    for ac in all_attempt_chats:
        if ac.profile_id:
            profile_ids_set.add(ac.profile_id)
        if ac.simulation_id:
            sim_ids_set.add(ac.simulation_id)
        if ac.scenario_id:
            scenario_ids_set.add(ac.scenario_id)

    # Step 4: Parallel hydrate resources

    async def _get_profiles() -> list:
        async with pool.acquire() as conn:
            return await get_profiles(conn, list(profile_ids_set), redis, bypass_cache)

    async def _get_simulations() -> list:
        async with pool.acquire() as conn:
            return await get_simulations(conn, list(sim_ids_set), redis, bypass_cache)

    async def _get_scenarios() -> list:
        async with pool.acquire() as conn:
            return await get_scenarios(
                conn, list(scenario_ids_set), redis, bypass_cache
            )

    profiles_selected, simulations_selected, scenarios_selected = await asyncio.gather(
        _get_profiles() if profile_ids_set else _empty_list(),
        _get_simulations() if sim_ids_set else _empty_list(),
        _get_scenarios() if scenario_ids_set else _empty_list(),
    )

    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=None,  # type: ignore[arg-type]
        draft_version=None,
        resources={
            "profiles": ResourcePair(selected=profiles_selected, suggestions=[]),
            "simulations": ResourcePair(selected=simulations_selected, suggestions=[]),
            "scenarios": ResourcePair(selected=scenarios_selected, suggestions=[]),
        },
        entries={
            "attempt_chats": all_attempt_chats,
            "attempt_messages": all_attempt_messages,
        },
    )


async def _empty_list() -> list:
    return []
