"""Test search logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments, name)
  2. search_tests — core MV search (items + total_count)
  3. Facets — parallel resource searches for filter options
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.test.types import (
    SearchTestApiResponse,
    SearchTestItem,
)
from app.infra.v5_types import ListFilterOption, ListFilterSection
from app.tools.entries.test.search import search_tests
from app.tools.resources.departments.search import search_departments
from app.tools.resources.evals.search import search_evals


async def search_test_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Main filters
    eval_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    is_archived: bool | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    # Facet search text
    eval_search: str | None = None,
    department_search: str | None = None,
    # Pagination
    page_size: int = 20,
    page_offset: int = 0,
) -> SearchTestApiResponse:
    """Test search using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, departments, name
      2. search_tests → (test items, total_count)
      3. Parallel: facets (eval filter, department filter)
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

    # ── Step 3: Search tests ───────────────────────────────────────────

    async with pool.acquire() as conn:
        items, total_count = await search_tests(
            conn,
            eval_ids=eval_ids,
            department_ids=department_ids,
            is_archived=is_archived,
            date_from=date_from,
            date_to=date_to,
            limit=page_size,
            offset=page_offset,
        )

    if not items:
        return _empty_response(actor_name, total_count=0)

    # ── Step 4: Parallel facets ────────────────────────────────────────

    async def _get_eval_facet() -> list:
        async with pool.acquire() as conn:
            return await search_evals(
                conn, redis, search=eval_search, eval=True, limit_count=100
            )

    async def _get_department_facet() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn, redis, search=department_search, eval=True, limit_count=100
            )

    eval_facet, department_facet = await asyncio.gather(
        _get_eval_facet(),
        _get_department_facet(),
    )

    # ── Step 5: Build test list ────────────────────────────────────────

    # Build eval lookup for hydrating names
    eval_map = {e.id: e for e in eval_facet}

    tests: list[SearchTestItem] = []

    for item in items:
        eval_obj = eval_map.get(item.eval_id) if item.eval_id else None

        tests.append(
            SearchTestItem(
                test_id=item.test_id,
                eval_id=item.eval_id,
                eval_name=eval_obj.name if eval_obj else None,
                eval_description=eval_obj.description if eval_obj else None,
                department_ids=item.department_ids if item.department_ids else None,
                test_name=item.test_name,
                test_description=item.test_description,
                num_invocations=item.num_invocations,
                infinite_mode=item.infinite_mode,
                is_dynamic=item.is_dynamic,
                archived=item.archived,
                created_at=item.test_created_at.isoformat()
                if item.test_created_at
                else None,
            )
        )

    # ── Step 6: Build facet sections ───────────────────────────────────

    eval_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(e.id), name=e.name, count=0) for e in eval_facet
        ],
        selected_ids=[str(eid) for eid in eval_ids] if eval_ids else None,
        search=eval_search,
    )

    department_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(d.id), name=d.name, count=0)
            for d in department_facet
        ],
        selected_ids=[str(did) for did in department_ids] if department_ids else None,
        search=department_search,
    )

    return SearchTestApiResponse(
        actor_name=actor_name,
        tests=tests,
        eval_filter=eval_filter,
        department_filter=department_filter,
        total_count=total_count,
    )


# ── Helpers ────────────────────────────────────────────────────────────


def _empty_response(
    actor_name: str | None = None, total_count: int = 0
) -> SearchTestApiResponse:
    return SearchTestApiResponse(
        actor_name=actor_name,
        tests=[],
        total_count=total_count,
    )
