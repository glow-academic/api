"""Hydrate ``ListEvalApiEval`` rows for a specific set of eval ids.

Used by create/duplicate/update impls to return the full row content
alongside their per-row status results — so the client's ghost rail can
materialize the new/changed row directly from the audit ``.completed``
payload, no ``router.refresh()`` needed (which would re-burst the page's
SSR fetches).

This is a focused subset of ``_search_eval_build``'s flow: the row
hydration steps (get artifacts → resolve junctions → hydrate names /
descriptions / flags → compute permissions), without the facet
aggregation, pagination, or big-cache wrap that the search route layers
on top.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.eval.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.eval.types import ListEvalApiEval
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.eval.get import get_evals
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.flags.get import get_flags
from app.tools.resources.names.get import get_names


async def hydrate_eval_list_rows(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    eval_ids: list[UUID],
) -> list[ListEvalApiEval]:
    """Return ``ListEvalApiEval`` rows for the given eval ids.

    Mirrors ``_search_eval_build``'s row-hydration steps minus facets
    and pagination. ``num_runs`` / ``num_groups`` are reported as None
    (the search endpoint also leaves them None today; reconciled on
    next page-level fetch).
    """
    if not eval_ids:
        return []

    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        return []

    user_role_level = profile.role_level

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
        )

    if not artifacts:
        return []

    # Resolve rubric_artifact_ids per model_rubrics_resource row (same
    # walk as ``_search_eval_build``): model_rubrics_resource.rubric_id
    # → rubrics_resource.id; reverse-walk rubric_rubrics_junction.
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

    # Collect resource ids to hydrate in parallel.
    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_flag_ids: list[UUID] = []
    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_flag_ids.extend(a.flag_ids or [])

    async def _names() -> list:
        return await get_names(pool, all_name_ids, redis) if all_name_ids else []

    async def _descs() -> list:
        return (
            await get_descriptions(pool, all_description_ids, redis)
            if all_description_ids
            else []
        )

    async def _flags() -> list:
        return await get_flags(pool, all_flag_ids, redis) if all_flag_ids else []

    names_data, descriptions_data, flags_data = await asyncio.gather(
        _names(), _descs(), _flags(),
    )

    name_map = {n.id: n for n in names_data}
    description_map = {d.id: d for d in descriptions_data}
    flag_map = {f.id: f for f in flags_data}

    rows: list[ListEvalApiEval] = []
    for a in artifacts:
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        desc_obj = (
            description_map.get(a.description_ids[0]) if a.description_ids else None
        )

        dept_ids_str = [str(d) for d in (a.department_ids or [])]

        artifact_flags = [
            flag_map[fid] for fid in (a.flag_ids or []) if fid in flag_map
        ]
        is_dynamic = any(f.name == "eval_dynamic" and f.value for f in artifact_flags)
        use_groups = any(f.name == "eval_groups" and f.value for f in artifact_flags)

        is_inactive = not a.active

        can_edit = compute_can_edit(
            role_level=user_role_level,
            role_permissions=profile.role_permissions,
        )
        can_delete = compute_can_delete(
            role_level=user_role_level,
            role_permissions=profile.role_permissions,
        )
        can_duplicate = compute_can_duplicate(
            role_level=user_role_level,
            role_permissions=profile.role_permissions,
        )

        # Aggregate rubric_artifact_ids across this eval's model_rubrics
        # rows (mirrors search.py).
        eval_rubric_ids: list[UUID] = []
        seen_rubric_ids: set[UUID] = set()
        for mr_id in a.model_rubric_ids or []:
            for rid in rubric_artifact_ids_by_model_rubric.get(mr_id, []):
                if rid not in seen_rubric_ids:
                    seen_rubric_ids.add(rid)
                    eval_rubric_ids.append(rid)

        rows.append(
            ListEvalApiEval(
                eval_id=a.id,
                name=name_obj.name if name_obj else None,
                description=desc_obj.description if desc_obj else None,
                department_ids=dept_ids_str,
                model_ids=list(a.model_ids or []),
                rubric_ids=eval_rubric_ids,
                is_inactive=is_inactive,
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

    return rows
