"""Resolve reports context — search_attempt_chats + resource hydration.

Reports is a search/analytics endpoint with no artifact table and no drafts.
Uses attempt_chat_mv as the sole data grain — same as dashboard.
"""

from __future__ import annotations

import asyncio
from datetime import date
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.identity.settings import resolve_thresholds
from app.infra.types import ArtifactContext, ResourcePair
from app.tools.entries.attempt_chat.search import search_attempt_chats
from app.tools.entries.attempt_chat.types import (
    ChatItem,
    GetAttemptChatResponse,
)
from app.tools.resources.cohorts.get import get_cohorts
from app.tools.resources.profiles.get import get_profiles
from app.tools.resources.scenarios.get import get_scenarios
from app.tools.resources.simulations.get import get_simulations


def _to_chat_item(r: GetAttemptChatResponse) -> ChatItem:
    """Convert a GetAttemptChatResponse (raw MV row) to ChatItem."""
    return ChatItem(
        chat_id=r.chat_id,
        attempt_id=r.attempt_id,
        chat_entry_id=r.chat_entry_id,
        group_id=r.group_id,
        attempt_chat_id=r.chat_entry_id,
        profile_id=r.profile_id,
        cohort_id=r.cohort_id,
        department_id=r.department_id,
        simulation_id=r.simulation_id,
        scenario_id=r.scenario_id,
        persona_ids=r.persona_ids,
        rubric_id=r.rubric_id,
        grade_score=r.grade_score,
        grade_total_points=r.grade_total_points,
        grade_pass_points=r.grade_pass_points,
        grade_passed=r.grade_passed,
        grade_time_taken=r.grade_time_taken,
        completed=r.completed or False,
        attempt_number=r.attempt_number or 0,
        chat_created_at=r.chat_created_at,
        attempt_date=r.attempt_date,
        attempt_type=r.attempt_type,
        is_archived=r.is_archived or False,
        infinite_mode=r.infinite_mode or False,
        document_ids=r.document_ids or [],
    )


async def resolve_reports_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    target_profile_id: UUID | None = None,
    actor_profile_id: UUID | None = None,
    cohort_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    simulation_ids: list[UUID] | None = None,
    attempt_type: str | None = None,
    is_archived: bool = False,
    date_from: date | None = None,
    date_to: date | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve reports context for search/analytics.

    Entries:
      - chat_items: ChatItem list from attempt_chat_mv
      - thresholds: [dict] (single-item list)

    Resources:
      - simulations, scenarios, profiles, cohorts
    """

    # ── Phase 1: Fetch chats + thresholds in parallel ────────────────
    async def _fetch_chats() -> list[ChatItem]:
        async with pool.acquire() as c:
            raw, _total_count = await search_attempt_chats(
                c,
                profile_ids=[target_profile_id] if target_profile_id else None,
                cohort_ids=cohort_ids,
                department_ids=list(department_ids) if department_ids else None,
                simulation_ids=simulation_ids,
                attempt_type=attempt_type,
                is_archived=is_archived,
                date_from=date_from,
                date_to=date_to,
                limit=100000,
            )
        return [_to_chat_item(r) for r in raw]

    async def _fetch_thresholds() -> dict[str, int | float]:
        profile_for_settings = actor_profile_id or target_profile_id
        return await resolve_thresholds(
            pool, redis, profile_for_settings, bypass_cache=bypass_cache
        )

    chat_items, thresholds = await asyncio.gather(
        _fetch_chats(),
        _fetch_thresholds(),
    )

    # ── Phase 2: Collect resource IDs from chat_items ────────────────
    simulation_ids_set: set[UUID] = set()
    profile_ids_set: set[UUID] = set()
    scenario_ids_set: set[UUID] = set()
    cohort_ids_set: set[UUID] = set()

    for item in chat_items:
        if item.simulation_id:
            simulation_ids_set.add(item.simulation_id)
        if item.profile_id:
            profile_ids_set.add(item.profile_id)
        if item.scenario_id:
            scenario_ids_set.add(item.scenario_id)
        if item.cohort_id:
            cohort_ids_set.add(item.cohort_id)

    # ── Phase 3: Parallel resource hydration ─────────────────────────
    async def _get_simulations() -> list:
        if not simulation_ids_set:
            return []
        async with pool.acquire() as c:
            return await get_simulations(
                c, list(simulation_ids_set), redis, bypass_cache=bypass_cache
            )

    async def _get_profiles() -> list:
        if not profile_ids_set:
            return []
        async with pool.acquire() as c:
            return await get_profiles(
                c, list(profile_ids_set), redis, bypass_cache=bypass_cache
            )

    async def _get_scenarios() -> list:
        if not scenario_ids_set:
            return []
        async with pool.acquire() as c:
            return await get_scenarios(
                c, list(scenario_ids_set), redis, bypass_cache=bypass_cache
            )

    async def _get_cohorts() -> list:
        if not cohort_ids_set:
            return []
        async with pool.acquire() as c:
            return await get_cohorts(
                c, list(cohort_ids_set), redis, bypass_cache=bypass_cache
            )

    simulations, profiles, scenarios, cohorts = await asyncio.gather(
        _get_simulations(),
        _get_profiles(),
        _get_scenarios(),
        _get_cohorts(),
    )

    # ── Phase 4: Return ArtifactContext ──────────────────────────────
    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=None,  # type: ignore[arg-type]
        draft_version=None,
        entries={
            "chat_items": chat_items,
            "thresholds": [thresholds],
        },
        resources={
            "simulations": ResourcePair(selected=simulations, suggestions=[]),
            "profiles": ResourcePair(selected=profiles, suggestions=[]),
            "scenarios": ResourcePair(selected=scenarios, suggestions=[]),
            "cohorts": ResourcePair(selected=cohorts, suggestions=[]),
        },
    )
