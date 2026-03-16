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

from app.infra.profile_identity_context import resolve_profile_identity_context
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
from app.infra.v5_types import ListFilterOption, ListFilterSection
from app.tools.artifacts.rubric.get import get_rubrics
from app.tools.artifacts.rubric.search import search_rubrics
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.names.get import get_names
from app.tools.resources.points.get import get_points
from app.tools.resources.simulations.search import (
    search_simulations as search_simulations_resource,
)
from app.tools.resources.standard_groups.get import get_standard_groups
from app.tools.resources.standards.get import get_standards

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
    # Main filters
    search: str | None = None,
    filter_department_ids: list[UUID] | None = None,
    filter_simulation_ids: list[UUID] | None = None,
    # Facet search text
    department_search: str | None = None,
    simulation_search: str | None = None,
    # Pagination
    page_size: int = 12,
    page_offset: int = 0,
) -> ListRubricApiResponse:
    """Rubric search using composable infra functions."""
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

    # ── Step 2: Reverse lookups ────────────────────────────────────────

    # simulation_ids can be passed directly to search_rubrics which has
    # built-in support for simulation_ids filter via scenario_rubrics_resource

    # ── Step 3: Search rubrics ────────────────────────────────────────

    async with pool.acquire() as conn:
        rubric_ids_list, total_count = await search_rubrics(
            conn,
            search=search,
            department_ids=filter_department_ids,
            simulation_ids=filter_simulation_ids,
            limit_count=page_size,
            offset_count=page_offset,
        )

    if not rubric_ids_list:
        return _empty_response(actor_name, total_count=0)

    # ── Step 4: Get rubric artifacts with junction IDs ────────────────

    async with pool.acquire() as conn:
        artifacts = await get_rubrics(
            conn,
            rubric_ids_list,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            points=True,
            standard_groups=True,
            standards=True,
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
        async with pool.acquire() as conn:
            return await get_names(conn, all_name_ids, redis)

    async def _get_descriptions() -> list:
        async with pool.acquire() as conn:
            return await get_descriptions(conn, all_description_ids, redis)

    async def _get_points() -> list:
        async with pool.acquire() as conn:
            return await get_points(conn, all_point_ids, redis)

    async def _get_standard_groups() -> list:
        async with pool.acquire() as conn:
            return await get_standard_groups(conn, all_standard_group_ids, redis)

    async def _get_standards() -> list:
        async with pool.acquire() as conn:
            return await get_standards(conn, all_standard_ids, redis)

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

    (
        names_data,
        descriptions_data,
        points_data,
        standard_groups_data,
        standards_data,
        department_facet,
        simulation_facet,
    ) = await asyncio.gather(
        _get_names() if all_name_ids else _empty_list(),
        _get_descriptions() if all_description_ids else _empty_list(),
        _get_points() if all_point_ids else _empty_list(),
        _get_standard_groups() if all_standard_group_ids else _empty_list(),
        _get_standards() if all_standard_ids else _empty_list(),
        _search_departments(),
        _search_simulations(),
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
            user_role=user_role,
            rubric_department_ids=dept_ids,
            active_simulation_count=0,
        )
        can_delete = compute_can_delete(
            user_role=user_role,
            rubric_department_ids=dept_ids,
            active_simulation_count=0,
        )
        can_duplicate = compute_can_duplicate(user_role=user_role)

        rubrics_list.append(
            ListRubricApiRubric(
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

    return ListRubricApiResponse(
        actor_name=actor_name,
        rubrics=rubrics_list,
        standard_groups=all_standard_groups_out,
        standards=all_standards_out,
        department_filter=department_filter,
        simulation_filter=simulation_filter,
        total_count=total_count,
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
    )


async def _empty_list() -> list:
    return []
