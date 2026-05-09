"""Hydrate ``ListRubricApiRubric`` rows for a specific set of rubric ids.

Used by create/duplicate/update impls to return the full row content
alongside their per-row status results — so the client's ghost rail can
materialize the new/changed row directly from the audit ``.completed``
payload, no ``router.refresh()`` needed (which would re-burst the page's
SSR fetches).

This is a focused subset of ``_search_rubric_build``'s flow: the row
hydration steps (get artifacts → resolve junctions → hydrate names /
descriptions / points / standard groups / standards → compute
permissions), without the facet aggregation, pagination, or big-cache
wrap that the search route layers on top.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.rubric.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.rubric.types import ListRubricApiRubric
from app.tools.artifacts.rubric.get import get_rubrics
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.names.get import get_names
from app.tools.resources.points.get import get_points
from app.tools.resources.standard_groups.get import get_standard_groups


async def hydrate_rubric_list_rows(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    rubric_ids: list[UUID],
) -> list[ListRubricApiRubric]:
    """Return ``ListRubricApiRubric`` rows for the given rubric ids.

    Mirrors ``_search_rubric_build``'s row-hydration steps minus facets
    and pagination. ``active_simulation_count`` is reported as 0 (the
    rubric is brand-new or just edited; simulation linkage count is
    server-side materialized and reconciles on next page-level search).
    Eval ids are computed from the same ``model_rubrics_resource`` join
    ``/rubric/search`` uses, so the eval column stays accurate for both
    fresh and updated rows.
    """
    if not rubric_ids:
        return []

    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        return []

    user_role_level = profile.role_level

    async with pool.acquire() as conn:
        artifacts = await get_rubrics(
            conn,
            rubric_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            points=True,
            standard_groups=True,
            standards=True,
            rubrics=True,
        )

    if not artifacts:
        return []

    # Per-rubric eval_ids map (eval_artifact ids referencing this rubric).
    # Path: rubric_artifact → rubrics_resource (a.rubric_ids) →
    # model_rubrics_resource (joined on rubric_id) →
    # eval_model_rubrics_junction → eval_artifact.id. Same query as
    # ``_search_rubric_build``.
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

    # Collect resource ids to hydrate in parallel.
    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_point_ids: list[UUID] = []
    all_standard_group_ids: list[UUID] = []
    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_point_ids.extend(a.point_ids or [])
        all_standard_group_ids.extend(a.standard_group_ids or [])

    async def _names() -> list:
        return await get_names(pool, all_name_ids, redis) if all_name_ids else []

    async def _descs() -> list:
        return await get_descriptions(pool, all_description_ids, redis) if all_description_ids else []

    async def _points() -> list:
        return await get_points(pool, all_point_ids, redis) if all_point_ids else []

    async def _standard_groups() -> list:
        return await get_standard_groups(pool, all_standard_group_ids, redis) if all_standard_group_ids else []

    names_data, descriptions_data, points_data, standard_groups_data = await asyncio.gather(
        _names(), _descs(), _points(), _standard_groups(),
    )

    name_map = {n.id: n for n in names_data}
    description_map = {d.id: d for d in descriptions_data}
    point_map = {p.id: p for p in points_data}
    sg_map = {sg.id: sg for sg in standard_groups_data}

    rows: list[ListRubricApiRubric] = []
    for a in artifacts:
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        desc_obj = description_map.get(a.description_ids[0]) if a.description_ids else None

        total_points: int | None = None
        if a.point_ids:
            point_obj = point_map.get(a.point_ids[0])
            if point_obj:
                total_points = point_obj.value

        dept_ids = [str(d) for d in (a.department_ids or [])]

        # pass_points / pass_percentage from standard groups (mirrors search)
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

        # Active simulation count is reconciled on the next page-level
        # search; for the freshly-written / updated row we report 0.
        active_simulation_count = 0

        can_edit = compute_can_edit(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            rubric_department_ids=dept_ids,
            active_simulation_count=active_simulation_count,
        )
        can_delete = compute_can_delete(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            rubric_department_ids=dept_ids,
            active_simulation_count=active_simulation_count,
        )
        can_duplicate = compute_can_duplicate(
            role_level=user_role_level, role_permissions=profile.role_permissions,
        )

        # Aggregate eval_ids across this rubric's rubrics_resource rows.
        rubric_eval_ids: list[UUID] = []
        seen_eval_ids: set[UUID] = set()
        for rr_id in a.rubric_ids or []:
            for eid in eval_ids_by_rubric_resource.get(rr_id, []):
                if eid not in seen_eval_ids:
                    seen_eval_ids.add(eid)
                    rubric_eval_ids.append(eid)

        rows.append(
            ListRubricApiRubric(
                rubric_id=a.id,
                name=name_obj.name if name_obj else None,
                description=desc_obj.description if desc_obj else None,
                points=total_points,
                pass_points=pass_points,
                pass_percentage=pass_percentage,
                department_ids=dept_ids,
                simulation_ids=None,
                active_simulation_count=active_simulation_count,
                can_edit=can_edit,
                can_delete=can_delete,
                can_duplicate=can_duplicate,
                standard_group_ids=rubric_sg_ids,
                eval_ids=rubric_eval_ids,
                is_inactive=not a.active,
            )
        )

    return rows
