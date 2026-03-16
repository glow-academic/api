"""Resolve practice context — raw MV reads + hydrated resources.

Practice is a dashboard endpoint with no artifact table and no drafts.
Access is cohort-based: user's profile → cohort search → filter practices.
No instructional mode — practice is always personal/member mode.

Two context resolvers:
  - resolve_practice_context: simulation cards (practice_mv + chat_mv + attempt_chat_mv)
  - resolve_practice_search_context: paginated history (attempt_mv + attempt_chat_mv)

Composes existing black-box fetchers — no raw SQL.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.types import ArtifactContext, ResourcePair

# Cohort search
from app.tools.artifacts.cohort.search import search_cohorts

# Entry fetchers (raw MV reads)
from app.tools.entries.attempt.search import search_attempts
from app.tools.entries.attempt_chat.search import search_attempt_chats
from app.tools.entries.chat.get import get_chats
from app.tools.entries.practice.search import search_practices

# Resource get fetchers
from app.tools.resources.cohorts.get import (
    get_cohorts as get_cohort_resources,
)
from app.tools.resources.personas.get import get_personas
from app.tools.resources.profiles.get import get_profiles
from app.tools.resources.rubrics.get import get_rubrics
from app.tools.resources.scenarios.get import get_scenarios
from app.tools.resources.simulations.get import get_simulations
from app.tools.resources.standard_groups.get import get_standard_groups
from app.tools.resources.standards.search import search_standards


async def resolve_practice_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profiles_resource_id: UUID,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve practice dashboard context for simulation cards.

    Entries (raw MVs):
      - practices: practice_mv rows (filtered by cohort overlap)
      - chats: chat_mv rows (rich per-chat config)
      - attempt_chats: attempt_chat_mv rows (cohort-scoped superset for personal + instructional)

    Resources (hydrated from IDs derived from chat_mv + practice_mv):
      - simulations, cohorts, personas, rubrics, standard_groups, standards
    """
    # Step 1: Resolve user's cohort IDs
    async with pool.acquire() as conn:
        user_cohort_ids, _total = await search_cohorts(
            conn,
            profile_ids=[profiles_resource_id],
            limit_count=1000,
        )

    # Step 2: Parallel raw MV reads (attempt_chats scoped by cohort for superset)

    async def _search_practices() -> list:
        async with pool.acquire() as conn:
            return await search_practices(conn, limit=10000)

    async def _search_attempt_chats() -> list:
        async with pool.acquire() as conn:
            return (
                await search_attempt_chats(
                    conn,
                    cohort_ids=user_cohort_ids,
                    limit=10000,
                )
            )[0]

    all_practices, all_attempt_chats = await asyncio.gather(
        _search_practices(),
        _search_attempt_chats() if user_cohort_ids else _empty_list(),
    )

    # Step 3: Filter practices by cohort overlap
    user_cohort_set = set(user_cohort_ids)
    filtered_practices = [
        p
        for p in all_practices
        if p.active and p.cohort_ids and user_cohort_set & set(p.cohort_ids)
    ]

    # Step 4: Collect chat_ids from filtered practices → get_chats (chat_mv)
    all_chat_ids: list[UUID] = []
    for p in filtered_practices:
        all_chat_ids.extend(p.chat_ids or [])
    chat_ids_deduped = list(dict.fromkeys(all_chat_ids))

    if chat_ids_deduped:
        async with pool.acquire() as conn:
            all_chats = await get_chats(conn, chat_ids_deduped)
    else:
        all_chats = []

    # Step 5: Derive resource IDs from entries
    simulation_ids: list[UUID] = []
    all_cohort_ids: set[UUID] = set()
    for p in filtered_practices:
        simulation_ids.extend(p.simulation_ids or [])
        all_cohort_ids.update(p.cohort_ids or [])

    simulation_ids_deduped = list(dict.fromkeys(simulation_ids))
    cohort_ids_list = list(all_cohort_ids)

    # From chat_mv entries
    all_persona_ids: set[UUID] = set()
    all_rubric_ids: set[UUID] = set()
    all_standard_group_ids: set[UUID] = set()
    for chat in all_chats:
        all_persona_ids.update(chat.persona_ids or [])
        all_rubric_ids.update(chat.rubric_ids or [])
        all_standard_group_ids.update(chat.standard_group_ids or [])

    # Step 6: Parallel hydrate resources

    async def _get_simulations() -> list:
        async with pool.acquire() as conn:
            return await get_simulations(
                conn, simulation_ids_deduped, redis, bypass_cache
            )

    async def _get_cohorts() -> list:
        async with pool.acquire() as conn:
            return await get_cohort_resources(
                conn, cohort_ids_list, redis, bypass_cache
            )

    async def _get_personas() -> list:
        async with pool.acquire() as conn:
            return await get_personas(conn, list(all_persona_ids), redis, bypass_cache)

    async def _get_rubrics() -> list:
        async with pool.acquire() as conn:
            return await get_rubrics(conn, list(all_rubric_ids), redis, bypass_cache)

    async def _get_standard_groups() -> list:
        async with pool.acquire() as conn:
            return await get_standard_groups(
                conn, list(all_standard_group_ids), redis, bypass_cache
            )

    async def _search_standards() -> list:
        async with pool.acquire() as conn:
            return await search_standards(
                conn,
                redis,
                standard_group_ids=list(all_standard_group_ids),
                bypass_cache=bypass_cache,
            )

    (
        simulations_selected,
        cohorts_selected,
        personas_selected,
        rubrics_selected,
        standard_groups_selected,
        standards_selected,
    ) = await asyncio.gather(
        _get_simulations() if simulation_ids_deduped else _empty_list(),
        _get_cohorts() if cohort_ids_list else _empty_list(),
        _get_personas() if all_persona_ids else _empty_list(),
        _get_rubrics() if all_rubric_ids else _empty_list(),
        _get_standard_groups() if all_standard_group_ids else _empty_list(),
        _search_standards() if all_standard_group_ids else _empty_list(),
    )

    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=None,  # type: ignore[arg-type]
        draft_version=None,
        resources={
            "simulations": ResourcePair(selected=simulations_selected, suggestions=[]),
            "cohorts": ResourcePair(selected=cohorts_selected, suggestions=[]),
            "personas": ResourcePair(selected=personas_selected, suggestions=[]),
            "rubrics": ResourcePair(selected=rubrics_selected, suggestions=[]),
            "standard_groups": ResourcePair(
                selected=standard_groups_selected, suggestions=[]
            ),
            "standards": ResourcePair(selected=standards_selected, suggestions=[]),
        },
        entries={
            "practices": filtered_practices,
            "chats": all_chats,
            "attempt_chats": all_attempt_chats,
        },
    )


async def resolve_practice_search_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profiles_resource_id: UUID,
    scenario_ids: list[UUID] | None = None,
    infinite_mode: bool | None = None,
    is_archived: bool | None = False,
    sort_order: str = "desc",
    page: int = 0,
    page_size: int = 20,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve practice search context for paginated history.

    Entries (raw MVs):
      - attempts: attempt_mv rows (paginated, filtered, practice=True)
      - attempt_chats: attempt_chat_mv rows (for grade aggregation)
      - total_attempts: all matching attempts (for total_count + filter options)

    Resources (hydrated for display names):
      - simulations, personas, scenarios, profiles
    """
    page_offset = page * page_size

    # Step 1: Paginated attempts
    async with pool.acquire() as conn:
        all_attempts, _total_count = await search_attempts(
            conn,
            profile_ids=[profiles_resource_id],
            practice=True,
            is_archived=is_archived,
            scenario_ids=scenario_ids,
            infinite_mode=infinite_mode,
            sort_order=sort_order,
            limit=page_size,
            offset=page_offset,
        )

    # Total count
    async with pool.acquire() as conn:
        total_attempts, total_count = await search_attempts(
            conn,
            profile_ids=[profiles_resource_id],
            practice=True,
            is_archived=is_archived,
            scenario_ids=scenario_ids,
            infinite_mode=infinite_mode,
            limit=100000,
            offset=0,
        )

    # Step 2: Fetch attempt_chats for paginated attempt_ids
    attempt_ids = [a.attempt_id for a in all_attempts]
    if attempt_ids:
        async with pool.acquire() as conn:
            all_attempt_chats = (
                await search_attempt_chats(conn, attempt_ids=attempt_ids, limit=10000)
            )[0]
    else:
        all_attempt_chats = []

    # Step 3: Collect resource IDs
    sim_ids: set[UUID] = set()
    profile_ids: set[UUID] = set()
    persona_ids: set[UUID] = set()
    scenario_ids_set: set[UUID] = set()

    for a in all_attempts:
        if a.simulation_id:
            sim_ids.add(a.simulation_id)
        if a.profile_id:
            profile_ids.add(a.profile_id)
        if a.scenario_ids:
            scenario_ids_set.update(a.scenario_ids)

    for ac in all_attempt_chats:
        if ac.persona_ids:
            persona_ids.update(ac.persona_ids)
        if ac.scenario_id:
            scenario_ids_set.add(ac.scenario_id)

    # Parallel hydrate

    async def _get_simulations() -> list:
        async with pool.acquire() as conn:
            return await get_simulations(conn, list(sim_ids), redis, bypass_cache)

    async def _get_profiles() -> list:
        async with pool.acquire() as conn:
            return await get_profiles(conn, list(profile_ids), redis, bypass_cache)

    async def _get_personas() -> list:
        async with pool.acquire() as conn:
            return await get_personas(conn, list(persona_ids), redis, bypass_cache)

    async def _get_scenarios() -> list:
        async with pool.acquire() as conn:
            return await get_scenarios(
                conn, list(scenario_ids_set), redis, bypass_cache
            )

    (
        simulations_selected,
        profiles_selected,
        personas_selected,
        scenarios_selected,
    ) = await asyncio.gather(
        _get_simulations() if sim_ids else _empty_list(),
        _get_profiles() if profile_ids else _empty_list(),
        _get_personas() if persona_ids else _empty_list(),
        _get_scenarios() if scenario_ids_set else _empty_list(),
    )

    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=None,  # type: ignore[arg-type]
        draft_version=None,
        resources={
            "simulations": ResourcePair(selected=simulations_selected, suggestions=[]),
            "profiles": ResourcePair(selected=profiles_selected, suggestions=[]),
            "personas": ResourcePair(selected=personas_selected, suggestions=[]),
            "scenarios": ResourcePair(selected=scenarios_selected, suggestions=[]),
        },
        entries={
            "attempts": all_attempts,
            "attempt_chats": all_attempt_chats,
            "total_attempts": total_attempts,
        },
    )


async def _empty_list() -> list:
    return []
