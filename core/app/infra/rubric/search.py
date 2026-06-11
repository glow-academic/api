"""Rubric search logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments, name)
  2. Reverse lookups — simulation_ids → rubric IDs (search_rubrics has simulation_ids)
  3. search_rubrics — core artifact search (IDs + total_count)
  4. get_rubrics — hydrate junction IDs
  5. Resource get tools — hydrate names, descriptions, points, standard_groups, standards
  6. Permissions — compute per-rubric can_edit, can_delete, can_duplicate
  7. Facets — parallel resource searches for filter options
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.api_types import ListFilterOption, ListFilterSection
from app.infra.artifact_scope import clamp_artifacts_to_actor_scope
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.infra.rubric.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.rubric.types import (
    ListRubricApiResponse,
    ListRubricApiRubric,
    ListRubricApiStandard,
    ListRubricApiStandardGroup,
)
from app.tools.artifacts.rubric.get import get_rubrics
from app.tools.artifacts.rubric.search import search_rubrics
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.get import get_names
from app.tools.resources.points.get import get_points
from app.tools.resources.simulations.search import (
    search_simulations as search_simulations_resource,
)
from app.tools.resources.standard_groups.get import get_standard_groups
from app.tools.resources.standards.get import get_standards
from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

RUBRIC_IMPORT_FIELDS: list[dict[str, Any]] = [
    {
        "key": "name",
        "label": "Name",
        "required": True,
        "example": "Clinical Skills Rubric",
        "description": "The rubric's display name",
    },
    {
        "key": "description",
        "label": "Description",
        "example": "Evaluates clinical skills...",
        "description": "Optional description",
    },
    {
        "key": "active_flag",
        "label": "Active",
        "type": "boolean",
        "example": "true",
        "description": "Whether the rubric is active (true/false)",
    },
    {
        "key": "departments",
        "label": "Departments",
        "multi": True,
        "example": "Nursing, Medicine",
        "description": "Comma-separated department names",
    },
]


async def search_rubric_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    search: str | None = None,
    filter_department_ids: list[UUID] | None = None,
    filter_simulation_ids: list[UUID] | None = None,
    department_search: str | None = None,
    simulation_search: str | None = None,
    flag_search: str | None = None,
    page_size: int = 12,
    page_offset: int = 0,
    bypass_cache: bool = False,
    **_kwargs,
) -> ListRubricApiResponse:
    """rubric search — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("rubric/search", {
            "profile_id": str(profile_id),
            "search": search,
            "filter_department_ids": [str(x) for x in filter_department_ids] if filter_department_ids else None,
            "filter_simulation_ids": [str(x) for x in filter_simulation_ids] if filter_simulation_ids else None,
            "department_search": department_search,
            "simulation_search": simulation_search,
            "flag_search": flag_search,
            "page_size": page_size,
            "page_offset": page_offset,
        }),
        tags=["search", "rubric", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ListRubricApiResponse,
        builder=lambda: _search_rubric_build(
            pool, redis,
            profile_id=profile_id,
            search=search,
            filter_department_ids=filter_department_ids,
            filter_simulation_ids=filter_simulation_ids,
            department_search=department_search,
            simulation_search=simulation_search,
            flag_search=flag_search,
            page_size=page_size,
            page_offset=page_offset,
        ),
        bypass_cache=bypass_cache,
    )


async def _search_rubric_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Main filters
    search: str | None = None,
    filter_department_ids: list[UUID] | None = None,
    filter_simulation_ids: list[UUID] | None = None,
    # Facet search text
    department_search: str | None = None,
    simulation_search: str | None = None,
    flag_search: str | None = None,
    # Pagination
    page_size: int = 12,
    page_offset: int = 0,
) -> ListRubricApiResponse:
    """Rubric search using composable infra functions."""
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

    # ── Step 2: Reverse lookups ────────────────────────────────────────

    # simulation_ids can be passed directly to search_rubrics which has
    # built-in support for simulation_ids filter via scenario_rubrics_resource

    # ── Step 3: Search rubrics ────────────────────────────────────────

    with timed("query"):
     async with pool.acquire() as conn:
        rubric_ids_list, total_count = await search_rubrics(
            conn,
            search=search,
            department_ids=filter_department_ids,
            simulation_ids=filter_simulation_ids,
            limit_count=page_size,
            offset_count=page_offset,
        )

        from app.tools.entries.soft_calls.search import search_soft_calls
        pending_entries = await search_soft_calls(
            conn, redis, artifact="rubric", status="pending", limit=1000,
        )
    pending_ledger_ids = [e.artifact_id for e in pending_entries]
    ledger_by_artifact_id = {e.artifact_id: e for e in pending_entries}

    merged_ids: list[UUID] = []
    seen: set[UUID] = set()
    for rid in [*rubric_ids_list, *pending_ledger_ids]:
        if rid in seen:
            continue
        seen.add(rid)
        merged_ids.append(rid)
    added = sum(1 for rid in pending_ledger_ids if rid not in set(rubric_ids_list))
    total_count = total_count + added

    if not merged_ids:
        return _empty_response(actor_name, total_count=0)

    # ── Step 4: Get rubric artifacts with junction IDs ────────────────

    async with pool.acquire() as conn:
        artifacts = await get_rubrics(
            conn,
            merged_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            points=True,
            standard_groups=True,
            standards=True,
            rubrics=True,
            active=None,
        )

    # -- Actor department-scope clamp --
    # Mirror this artifact's DETAIL ``get`` ``has_access`` gate on the LIST
    # path so cross-department rows the caller could not open in detail are
    # not leaked here; ``total_count`` is decremented by the rows removed.
    artifacts, total_count = clamp_artifacts_to_actor_scope(
        artifacts, user_role_level, profile.department_ids, total_count
    )


    # Build per-rubric eval_ids map (eval_artifact ids referencing this rubric).
    # Path: rubric_artifact → rubrics_resource (a.rubric_ids) → model_rubrics_resource
    # (joined on rubric_id) → eval_model_rubrics_junction → eval_artifact.id.
    eval_ids_by_rubric_resource: dict[UUID, list[UUID]] = {}
    all_rubric_resource_ids: list[UUID] = []
    for a in artifacts:
        all_rubric_resource_ids.extend(a.rubric_ids or [])
    if all_rubric_resource_ids:
        async with pool.acquire() as conn:
            eval_rows = await conn.fetch(
                """
                SELECT mrr.rubric_id AS rubric_resource_id,
                       ARRAY_AGG(DISTINCT emrj.eval_id)
                         FILTER (WHERE emrj.eval_id IS NOT NULL) AS eval_ids
                FROM model_rubrics_resource mrr
                LEFT JOIN eval_model_rubrics_junction emrj
                  ON emrj.model_rubrics_id = mrr.id AND emrj.active = true
                WHERE mrr.rubric_id = ANY($1) AND mrr.active = true
                GROUP BY mrr.rubric_id
                """,
                all_rubric_resource_ids,
            )
        for r in eval_rows:
            eval_ids_by_rubric_resource[r["rubric_resource_id"]] = list(
                r["eval_ids"] or []
            )

    # ── Step 5: Parallel hydration + facets ────────────────────────────

    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_point_ids: list[UUID] = []
    all_standard_group_ids: list[UUID] = []
    all_standard_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_point_ids.extend(a.point_ids or [])
        all_standard_group_ids.extend(a.standard_group_ids or [])
        all_standard_ids.extend(a.standard_ids or [])

    async def _get_names() -> list:
        return await get_names(pool, all_name_ids, redis)

    async def _get_descriptions() -> list:
        return await get_descriptions(pool, all_description_ids, redis)

    async def _get_points() -> list:
        return await get_points(pool, all_point_ids, redis)

    async def _get_standard_groups() -> list:
        return await get_standard_groups(pool, all_standard_group_ids, redis)

    async def _get_standards() -> list:
        return await get_standards(pool, all_standard_ids, redis)

    async def _search_departments() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn, redis, search=department_search, rubric=True, limit_count=100
            )

    async def _search_simulations() -> list:
        async with pool.acquire() as conn:
            return await search_simulations_resource(
                conn, redis, search=simulation_search, simulation=True, limit_count=100
            )

    async def _search_flags() -> list:
        async with pool.acquire() as conn:
            return await search_flags(
                conn, redis, search=flag_search, rubric=True, limit_count=100
            )

    with timed("hydrate"):
     (
        names_data,
        descriptions_data,
        points_data,
        standard_groups_data,
        standards_data,
        department_facet,
        simulation_facet,
        flag_facet,
     ) = await asyncio.gather(
        _get_names() if all_name_ids else _empty_list(),
        _get_descriptions() if all_description_ids else _empty_list(),
        _get_points() if all_point_ids else _empty_list(),
        _get_standard_groups() if all_standard_group_ids else _empty_list(),
        _get_standards() if all_standard_ids else _empty_list(),
        _search_departments(),
        _search_simulations(),
        _search_flags(),
    )

    # Build lookup maps
    name_map = {n.id: n for n in names_data}
    description_map = {d.id: d for d in descriptions_data}
    point_map = {p.id: p for p in points_data}
    sg_map = {sg.id: sg for sg in standard_groups_data}
    std_map = {s.id: s for s in standards_data}

    # ── Step 6: Build rubric list with permissions + hierarchical data ──

    rubrics_list: list[ListRubricApiRubric] = []
    all_standard_groups_out: list[ListRubricApiStandardGroup] = []
    all_standards_out: list[ListRubricApiStandard] = []

    with timed("build"):
     for a in artifacts:
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        desc_obj = (
            description_map.get(a.description_ids[0]) if a.description_ids else None
        )

        # Resolve points from points_resource
        total_points: int | None = None
        if a.point_ids:
            point_obj = point_map.get(a.point_ids[0])
            if point_obj:
                total_points = point_obj.value

        dept_ids = [str(d) for d in (a.department_ids or [])]

        # Compute pass_points and pass_percentage from standard groups
        pass_points: int | None = None
        pass_percentage: int | None = None
        rubric_sg_ids = a.standard_group_ids or []
        if rubric_sg_ids:
            pp = 0
            for sg_id in rubric_sg_ids:
                sg = sg_map.get(sg_id)
                if sg:
                    pp += sg.pass_points
            pass_points = pp
            if total_points and total_points > 0:
                pass_percentage = int((pp / total_points) * 100)

        # Build standard_groups for this rubric
        for sg_id in rubric_sg_ids:
            sg = sg_map.get(sg_id)
            if sg:
                all_standard_groups_out.append(
                    ListRubricApiStandardGroup(
                        standard_group_id=sg.id,
                        rubric_id=a.id,
                        name=sg.name,
                        description=sg.description,
                        points=sg.points,
                        pass_points=sg.pass_points,
                    )
                )

        # Build standards for this rubric
        for std_id in a.standard_ids or []:
            std = std_map.get(std_id)
            if std:
                all_standards_out.append(
                    ListRubricApiStandard(
                        standard_id=std.id,
                        standard_group_id=std.standard_group_id,
                        name=std.name,
                        description=std.description,
                        points=std.points,
                    )
                )

        can_edit = compute_can_edit(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            rubric_department_ids=dept_ids,
            active_simulation_count=0,
        )
        can_delete = compute_can_delete(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            rubric_department_ids=dept_ids,
            active_simulation_count=0,
        )
        can_duplicate = compute_can_duplicate(role_level=user_role_level, role_permissions=profile.role_permissions)

        # Aggregate eval_ids across this rubric's rubrics_resource rows.
        rubric_eval_ids: list[UUID] = []
        seen_eval_ids: set[UUID] = set()
        for rr_id in a.rubric_ids or []:
            for eid in eval_ids_by_rubric_resource.get(rr_id, []):
                if eid not in seen_eval_ids:
                    seen_eval_ids.add(eid)
                    rubric_eval_ids.append(eid)

        ledger = ledger_by_artifact_id.get(a.id)
        rubrics_list.append(
            ListRubricApiRubric(
                id=a.id,

                rubric_id=a.id,
                name=name_obj.name if name_obj else None,
                description=desc_obj.description if desc_obj else None,
                points=total_points,
                pass_points=pass_points,
                pass_percentage=pass_percentage,
                department_ids=dept_ids,
                simulation_ids=None,
                active_simulation_count=0,
                can_edit=can_edit,
                can_delete=can_delete,
                can_duplicate=can_duplicate,
                standard_group_ids=rubric_sg_ids,
                eval_ids=rubric_eval_ids,
                is_inactive=not a.active,
                pending_status=ledger.status if ledger else None,
                pending_operation=ledger.operation if ledger else None,
                pending_call_id=ledger.call_id if ledger else None,
            )
        )

    # ── Step 7: Build facet sections ───────────────────────────────────

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

    simulation_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(s.id), name=s.name, count=0)
            for s in simulation_facet
        ],
        selected_ids=[str(sid) for sid in filter_simulation_ids]
        if filter_simulation_ids
        else None,
        search=simulation_search,
    )

    flag_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(f.id), name=f.name, type=f.type, count=0)
            for f in flag_facet
        ],
        search=flag_search,
    )

    return ListRubricApiResponse(
        actor_name=actor_name,
        rubrics=rubrics_list,
        standard_groups=all_standard_groups_out,
        standards=all_standards_out,
        department_filter=department_filter,
        simulation_filter=simulation_filter,
        flag_filter=flag_filter,
        total_count=total_count,
        import_fields=RUBRIC_IMPORT_FIELDS,
    )


# ── Helpers ────────────────────────────────────────────────────────────


def _empty_response(
    actor_name: str | None = None, total_count: int = 0
) -> ListRubricApiResponse:
    return ListRubricApiResponse(
        actor_name=actor_name,
        rubrics=[],
        standard_groups=[],
        standards=[],
        total_count=total_count,
        import_fields=RUBRIC_IMPORT_FIELDS,
    )


async def _empty_list() -> list:
    return []
