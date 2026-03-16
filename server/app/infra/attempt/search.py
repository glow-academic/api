"""Attempt search logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments, name)
  2. search_attempts — core MV search (IDs + total_count)
  3. Facets — parallel resource searches for filter options
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.attempt.types import (
    SearchAttemptApiResponse,
    SearchAttemptItem,
)
from app.infra.v5_types import ListFilterOption, ListFilterSection
from app.tools.entries.attempt.search import search_attempts
from app.tools.resources.departments.search import search_departments
from app.tools.resources.simulations.search import search_simulations


async def search_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Main filters
    search: str | None = None,
    simulation_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    practice: bool | None = None,
    is_archived: bool | None = None,
    infinite_mode: bool | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    # Facet search text
    simulation_search: str | None = None,
    department_search: str | None = None,
    # Pagination
    page_size: int = 20,
    page_offset: int = 0,
) -> SearchAttemptApiResponse:
    """Attempt search using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, departments, name
      2. search_attempts → (attempt items, total_count)
      3. Parallel: facets (simulation filter, department filter)
    """
    from datetime import datetime

    from fastapi import HTTPException

    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    actor_name = profile.name

    # ── Step 2: Parse dates ────────────────────────────────────────────

    date_from = None
    date_to = None
    if start_date:
        date_from = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
    if end_date:
        date_to = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

    # ── Step 3: Search attempts ────────────────────────────────────────

    async with pool.acquire() as conn:
        items, total_count = await search_attempts(
            conn,
            simulation_ids=simulation_ids,
            department_ids=department_ids,
            practice=practice,
            is_archived=is_archived,
            infinite_mode=infinite_mode,
            date_from=date_from,
            date_to=date_to,
            limit=page_size,
            offset=page_offset,
        )

    if not items:
        return _empty_response(actor_name, total_count=0)

    # ── Step 4: Parallel facets ────────────────────────────────────────

    async def _get_simulation_facet() -> list:
        async with pool.acquire() as conn:
            return await search_simulations(
                conn, redis, search=simulation_search, simulation=True, limit_count=100
            )

    async def _get_department_facet() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn, redis, search=department_search, simulation=True, limit_count=100
            )

    simulation_facet, department_facet = await asyncio.gather(
        _get_simulation_facet(),
        _get_department_facet(),
    )

    # ── Step 5: Build attempt list ─────────────────────────────────────

    attempts: list[SearchAttemptItem] = []

    for item in items:
        attempts.append(
            SearchAttemptItem(
                attempt_id=item.attempt_id,
                date=item.attempt_created_at.isoformat()
                if item.attempt_created_at
                else None,
                profile_id=item.profile_id,
                simulation_id=item.simulation_id,
                department_id=item.department_id,
                cohort_id=item.cohort_id,
                practice=item.practice,
                infinite_mode=item.infinite_mode,
                num_chats=item.num_chats,
                is_archived=item.is_archived,
                scenario_ids=item.scenario_ids if item.scenario_ids else None,
            )
        )

    # ── Step 6: Build facet sections ───────────────────────────────────

    simulation_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(s.id), name=s.name, count=0)
            for s in simulation_facet
        ],
        selected_ids=[str(sid) for sid in simulation_ids] if simulation_ids else None,
        search=simulation_search,
    )

    department_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(d.id), name=d.name, count=0)
            for d in department_facet
        ],
        selected_ids=[str(did) for did in department_ids] if department_ids else None,
        search=department_search,
    )

    return SearchAttemptApiResponse(
        actor_name=actor_name,
        attempts=attempts,
        simulation_filter=simulation_filter,
        department_filter=department_filter,
        total_count=total_count,
    )


# ── Helpers ────────────────────────────────────────────────────────────


def _empty_response(
    actor_name: str | None = None, total_count: int = 0
) -> SearchAttemptApiResponse:
    return SearchAttemptApiResponse(
        actor_name=actor_name,
        attempts=[],
        total_count=total_count,
    )
