"""Eval search logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments, name)
  2. search_evals (artifact) — core artifact search (IDs + total_count)
  3. get_evals (artifact) — hydrate junction IDs
  4. Resource get tools — hydrate names, descriptions
  5. Permissions — compute per-eval can_edit, can_delete, can_duplicate
  6. Facets — department search for filter options
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.eval.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.eval.types import (
    ListEvalApiEval,
    ListEvalApiResponse,
)
from app.infra.v5_types import ListFilterOption, ListFilterSection
from app.tools.artifacts.eval.get import get_evals
from app.tools.artifacts.eval.search import (
    search_evals as search_eval_artifacts,
)
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.flags.get import get_flags
from app.tools.resources.names.get import get_names

EVAL_IMPORT_FIELDS: list[dict[str, Any]] = [
    {
        "key": "name",
        "label": "Name",
        "required": True,
        "example": "Midterm Evaluation",
        "description": "The eval's display name",
    },
    {
        "key": "description",
        "label": "Description",
        "example": "Evaluates clinical reasoning skills...",
        "description": "Optional description",
    },
    {
        "key": "departments",
        "label": "Departments",
        "multi": True,
        "example": "Nursing, Medicine",
        "description": "Comma-separated department names",
    },
]


async def search_eval_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Main filters
    search: str | None = None,
    filter_department_ids: list[UUID] | None = None,
    # Facet search text
    department_search: str | None = None,
    # Pagination
    page_size: int = 50,
    page_offset: int = 0,
) -> ListEvalApiResponse:
    """Eval search using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, departments, name
      2. search_evals → (eval_artifact_ids, total_count)
      3. get_evals → hydrate junction IDs
      4. Parallel: hydrate resources + facets + eval metadata
      5. Compute permissions per eval
    """
    from fastapi import HTTPException

    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    user_role = profile.role
    actor_name = profile.name

    # ── Step 2: Search evals ──────────────────────────────────────────

    async with pool.acquire() as conn:
        eval_ids, total_count = await search_eval_artifacts(
            conn,
            search=search,
            department_ids=filter_department_ids,
            limit_count=page_size,
            offset_count=page_offset,
        )

    if not eval_ids:
        # Still fetch facets for empty results
        async with pool.acquire() as conn:
            department_facet = await search_departments(
                conn, redis, search=department_search, eval=True, limit_count=100
            )

        department_filter = ListFilterSection(
            options=[
                ListFilterOption(id=str(d.id), name=d.name, count=0)
                for d in department_facet
            ],
            selected_ids=[str(did) for did in filter_department_ids]
            if filter_department_ids
            else None,
            search=department_search,
        )

        return ListEvalApiResponse(
            actor_name=actor_name,
            evals=[],
            department_filter=department_filter,
            total_count=0,
            user_role=user_role,
        )

    # ── Step 3: Get eval artifacts with junction IDs ──────────────────

    async with pool.acquire() as conn:
        artifacts = await get_evals(
            conn,
            eval_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
        )

    # ── Step 4: Parallel hydration + facets ────────────────────────────

    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_flag_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_flag_ids.extend(a.flag_ids or [])

    async def _fetch_names() -> list:
        if not all_name_ids:
            return []
        async with pool.acquire() as conn:
            return await get_names(conn, all_name_ids, redis)

    async def _fetch_descriptions() -> list:
        if not all_description_ids:
            return []
        async with pool.acquire() as conn:
            return await get_descriptions(conn, all_description_ids, redis)

    async def _fetch_flags() -> list:
        if not all_flag_ids:
            return []
        async with pool.acquire() as conn:
            return await get_flags(conn, all_flag_ids, redis)

    async def _fetch_department_facet() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn, redis, search=department_search, eval=True, limit_count=100
            )

    (
        names_data,
        descriptions_data,
        flags_data,
        department_facet,
    ) = await asyncio.gather(
        _fetch_names(),
        _fetch_descriptions(),
        _fetch_flags(),
        _fetch_department_facet(),
    )

    flag_map = {f.id: f for f in flags_data}

    # Build lookup maps
    name_map = {n.id: n for n in names_data}
    description_map = {d.id: d for d in descriptions_data}

    # ── Step 5: Build eval list with permissions ──────────────────────

    evals_list: list[ListEvalApiEval] = []

    for a in artifacts:
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        desc_obj = (
            description_map.get(a.description_ids[0]) if a.description_ids else None
        )

        dept_ids_str = [str(d) for d in (a.department_ids or [])]

        # Resolve flags for this eval
        artifact_flags = [
            flag_map[fid] for fid in (a.flag_ids or []) if fid in flag_map
        ]
        is_dynamic = any(f.name == "eval_dynamic" and f.value for f in artifact_flags)
        use_groups = any(f.name == "eval_groups" and f.value for f in artifact_flags)

        can_edit = compute_can_edit(user_role=user_role)
        can_delete = compute_can_delete(user_role=user_role)
        can_duplicate = compute_can_duplicate(user_role)

        evals_list.append(
            ListEvalApiEval(
                eval_id=a.id,
                name=name_obj.name if name_obj else None,
                description=desc_obj.description if desc_obj else None,
                department_ids=dept_ids_str,
                is_inactive=not a.active,
                is_dynamic=is_dynamic,
                use_groups=use_groups,
                num_runs=None,
                num_groups=None,
                can_edit=can_edit,
                can_duplicate=can_duplicate,
                can_delete=can_delete,
                updated_at=a.updated_at,
            )
        )

    # ── Step 6: Build facet sections ──────────────────────────────────

    department_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(d.id), name=d.name, count=0)
            for d in department_facet
        ],
        selected_ids=[str(did) for did in filter_department_ids]
        if filter_department_ids
        else None,
        search=department_search,
    )

    return ListEvalApiResponse(
        actor_name=actor_name,
        evals=evals_list,
        department_filter=department_filter,
        total_count=total_count,
        user_role=user_role,
    )


# ── Helpers ────────────────────────────────────────────────────────────


async def _empty_list() -> list:
    return []
