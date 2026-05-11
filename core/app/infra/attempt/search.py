"""Canonical paginated attempt-history search.

This is the single endpoint clients use for paginated attempt rows across
home / practice / dashboard / record views. Filter shape is unified:
callers pass ``practice``, ``target_profile_id``, ``profile_ids``, etc. and
receive the same ``HistoryResponse`` shape regardless of view.

The previous per-view ``/attempt/{home,practice,dashboard}/search`` routes
were collapsed into this one. View intent is now expressed entirely through
filter parameters (e.g. ``practice=False`` for home, ``practice=True`` for
practice, ``target_profile_id=...`` for record).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.api_types import HistoryResponse
from app.infra.attempt.history import build_history_response
from app.infra.common_context import resolve_common_context
from app.infra.dashboard.context import resolve_dashboard_search_context
from app.infra.dashboard.visibility import resolve_visible_profile_ids


async def search_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Visibility / scoping
    target_profile_id: UUID | None = None,
    profile_ids: list[UUID] | None = None,
    # Filters
    cohort_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    role_ids: list[UUID] | None = None,
    simulation_ids: list[UUID] | None = None,
    scenario_ids: list[UUID] | None = None,
    practice: bool | None = None,
    infinite_mode: bool | None = None,
    show_archived: bool = False,
    start_date: str | None = None,
    end_date: str | None = None,
    # Text search
    simulation_search: str | None = None,
    scenario_search: str | None = None,
    profile_search: str | None = None,
    # Sort / pagination
    sort_by: str = "date",
    sort_order: str = "desc",
    page: int = 0,
    page_size: int = 20,
    bypass_cache: bool = False,
) -> HistoryResponse:
    """Canonical paginated attempt history.

    Visibility: ``profile_ids`` is intersected with the actor's visible-profile
    set so a caller can never widen the visibility scope by guessing UUIDs.
    """
    # ── Step 1: Profile context + visibility ──────────────────────────
    common = await resolve_common_context(
        pool, redis, profile_id=profile_id, bypass_cache=bypass_cache
    )
    if common is None:
        raise HTTPException(
            status_code=401, detail="Profile not found. Please sign in again."
        )

    visible_profile_ids = await resolve_visible_profile_ids(pool, common.profile)

    scoped_profile_ids: list[UUID] | None = visible_profile_ids
    if profile_ids and visible_profile_ids is not None:
        visible_set = set(visible_profile_ids)
        scoped_profile_ids = [pid for pid in profile_ids if pid in visible_set]

    # ── Step 2: Parse dates ───────────────────────────────────────────
    date_from = None
    date_to = None
    if start_date:
        date_from = datetime.fromisoformat(start_date.replace("Z", "+00:00")).date()
    if end_date:
        date_to = datetime.fromisoformat(end_date.replace("Z", "+00:00")).date()

    # ── Step 3: Resolve context ───────────────────────────────────────
    ctx = await resolve_dashboard_search_context(
        pool,
        redis,
        profile_resource_ids=scoped_profile_ids,
        target_profile_id=target_profile_id,
        cohort_ids=cohort_ids,
        department_ids=department_ids,
        role_ids=role_ids,
        practice=practice,
        scenario_ids=scenario_ids,
        simulation_ids=simulation_ids,
        infinite_mode=infinite_mode,
        show_archived=show_archived,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
        date_from=date_from,
        date_to=date_to,
        bypass_cache=bypass_cache,
    )

    # ── Step 4: Build response ────────────────────────────────────────
    return build_history_response(
        ctx,
        practice=practice,
        simulation_search=simulation_search,
        scenario_search=scenario_search,
        profile_search=profile_search,
        page=page,
        page_size=page_size,
    )
