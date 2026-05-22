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

from app.infra.api_types import ListFilterOption, ListFilterSection
from app.infra.eval.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.eval.types import (
    ListEvalApiEval,
    ListEvalApiResponse,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.artifacts.eval.get import get_evals
from app.tools.artifacts.eval.search import (
    search_evals as search_eval_artifacts,
)
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.flags.get import get_flags
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.get import get_names
from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

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
    search: str | None = None,
    filter_department_ids: list[UUID] | None = None,
    department_search: str | None = None,
    flag_search: str | None = None,
    page_size: int = 50,
    page_offset: int = 0,
    bypass_cache: bool = False,
    **_kwargs,
) -> ListEvalApiResponse:
    """eval search — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("eval/search", {
            "profile_id": str(profile_id),
            "search": search,
            "filter_department_ids": [str(x) for x in filter_department_ids] if filter_department_ids else None,
            "department_search": department_search,
            "flag_search": flag_search,
            "page_size": page_size,
            "page_offset": page_offset,
        }),
        tags=["search", "eval", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ListEvalApiResponse,
        builder=lambda: _search_eval_build(
            pool, redis,
            profile_id=profile_id,
            search=search,
            filter_department_ids=filter_department_ids,
            department_search=department_search,
            flag_search=flag_search,
            page_size=page_size,
            page_offset=page_offset,
        ),
        bypass_cache=bypass_cache,
    )


async def _search_eval_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Main filters
    search: str | None = None,
    filter_department_ids: list[UUID] | None = None,
    # Facet search text
    department_search: str | None = None,
    flag_search: str | None = None,
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

    with timed("profile"):
        profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    user_role_level = profile.role_level
    actor_name = profile.name

    # ── Step 2: Search evals ──────────────────────────────────────────

    with timed("query"):
     async with pool.acquire() as conn:
        eval_ids, total_count = await search_eval_artifacts(
            conn,
            search=search,
            department_ids=filter_department_ids,
            limit_count=page_size,
            offset_count=page_offset,
        )

        from app.tools.entries.soft_calls.search import search_soft_calls
        pending_entries = await search_soft_calls(
            conn, redis, artifact="eval", status="pending", limit=1000,
        )
    pending_ledger_ids = [e.artifact_id for e in pending_entries]
    ledger_by_artifact_id = {e.artifact_id: e for e in pending_entries}

    merged_ids: list[UUID] = []
    seen: set[UUID] = set()
    for eid in [*eval_ids, *pending_ledger_ids]:
        if eid in seen:
            continue
        seen.add(eid)
        merged_ids.append(eid)
    added = sum(1 for eid in pending_ledger_ids if eid not in set(eval_ids))
    total_count = total_count + added
    eval_ids = merged_ids

    if not eval_ids:
        # Still fetch facets for empty results
        async with pool.acquire() as conn:
            department_facet = await search_departments(
                conn, redis, search=department_search, eval=True, limit_count=100
            )
            flag_facet = await search_flags(
                conn, redis, search=flag_search, eval=True, limit_count=100
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

        flag_filter = ListFilterSection(
            options=[
                ListFilterOption(id=str(f.id), name=f.name, type=f.type, count=0)
                for f in flag_facet
            ],
            search=flag_search,
        )

        return ListEvalApiResponse(
            actor_name=actor_name,
            evals=[],
            department_filter=department_filter,
            flag_filter=flag_filter,
            total_count=0,
            user_role=profile.role,
            import_fields=EVAL_IMPORT_FIELDS,
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
            models=True,
            model_rubrics=True,
            active=None,
        )

    # Resolve rubric_artifact_ids per model_rubrics_resource row:
    # model_rubrics_resource.rubric_id → rubrics_resource.id; reverse-walk
    # rubric_rubrics_junction.rubrics_id → rubric_artifact.id.
    rubric_artifact_ids_by_model_rubric: dict[UUID, list[UUID]] = {}
    all_model_rubric_ids: list[UUID] = []
    for a in artifacts:
        all_model_rubric_ids.extend(a.model_rubric_ids or [])
    if all_model_rubric_ids:
        async with pool.acquire() as conn:
            mr_rows = await conn.fetch(
                """
                SELECT mrr.id AS model_rubric_id,
                       ARRAY_AGG(DISTINCT rrj.rubric_id)
                         FILTER (WHERE rrj.rubric_id IS NOT NULL) AS rubric_ids
                FROM model_rubrics_resource mrr
                LEFT JOIN rubric_rubrics_junction rrj
                  ON rrj.rubrics_id = mrr.rubric_id AND rrj.active = true
                WHERE mrr.id = ANY($1) AND mrr.active = true
                GROUP BY mrr.id
                """,
                all_model_rubric_ids,
            )
        for r in mr_rows:
            rubric_artifact_ids_by_model_rubric[r["model_rubric_id"]] = list(
                r["rubric_ids"] or []
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
        return await get_names(pool, all_name_ids, redis)

    async def _fetch_descriptions() -> list:
        if not all_description_ids:
            return []
        return await get_descriptions(pool, all_description_ids, redis)

    async def _fetch_flags() -> list:
        if not all_flag_ids:
            return []
        return await get_flags(pool, all_flag_ids, redis)

    async def _fetch_department_facet() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn, redis, search=department_search, eval=True, limit_count=100
            )

    async def _fetch_flag_facet() -> list:
        async with pool.acquire() as conn:
            return await search_flags(
                conn, redis, search=flag_search, eval=True, limit_count=100
            )

    with timed("hydrate"):
        (
            names_data,
            descriptions_data,
            flags_data,
            department_facet,
            flag_facet,
        ) = await asyncio.gather(
            _fetch_names(),
            _fetch_descriptions(),
            _fetch_flags(),
            _fetch_department_facet(),
            _fetch_flag_facet(),
        )

    flag_map = {f.id: f for f in flags_data}

    # Build lookup maps
    name_map = {n.id: n for n in names_data}
    description_map = {d.id: d for d in descriptions_data}

    # ── Step 5: Build eval list with permissions ──────────────────────

    evals_list: list[ListEvalApiEval] = []

    with timed("build"):
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

        can_edit = compute_can_edit(role_level=user_role_level, role_permissions=profile.role_permissions)
        can_delete = compute_can_delete(role_level=user_role_level, role_permissions=profile.role_permissions)
        can_duplicate = compute_can_duplicate(role_level=user_role_level, role_permissions=profile.role_permissions)

        # Aggregate rubric_artifact_ids across this eval's model_rubrics rows.
        eval_rubric_ids: list[UUID] = []
        seen_rubric_ids: set[UUID] = set()
        for mr_id in a.model_rubric_ids or []:
            for rid in rubric_artifact_ids_by_model_rubric.get(mr_id, []):
                if rid not in seen_rubric_ids:
                    seen_rubric_ids.add(rid)
                    eval_rubric_ids.append(rid)

        ledger = ledger_by_artifact_id.get(a.id)
        evals_list.append(
            ListEvalApiEval(
                eval_id=a.id,
                name=name_obj.name if name_obj else None,
                description=desc_obj.description if desc_obj else None,
                department_ids=dept_ids_str,
                model_ids=list(a.model_ids or []),
                rubric_ids=eval_rubric_ids,
                is_inactive=not a.active,
                is_dynamic=is_dynamic,
                use_groups=use_groups,
                pending_status=ledger.status if ledger else None,
                pending_operation=ledger.operation if ledger else None,
                pending_call_id=ledger.call_id if ledger else None,
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

    flag_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(f.id), name=f.name, type=f.type, count=0)
            for f in flag_facet
        ],
        search=flag_search,
    )

    return ListEvalApiResponse(
        actor_name=actor_name,
        evals=evals_list,
        department_filter=department_filter,
        flag_filter=flag_filter,
        total_count=total_count,
        user_role=profile.role,
        import_fields=EVAL_IMPORT_FIELDS,
    )


# ── Helpers ────────────────────────────────────────────────────────────


async def _empty_list() -> list:
    return []
