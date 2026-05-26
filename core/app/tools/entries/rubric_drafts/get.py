"""Rubric drafts GET — read from base table + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.rubric_drafts.types import GetRubricDraftResponse
from app.utils.cache.hedged_row import read_back_row


async def get_rubric_drafts(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    active: bool | None = True,
    *,
    bypass_cache: bool = False,
) -> list[GetRubricDraftResponse]:
    """Get rubric_drafts entries by IDs with connection data.

    ``active=None`` returns dormant + active rows.
    """
    if not ids:
        return []

    cached_results: dict[str, GetRubricDraftResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for rid in ids:
            cached = await read_back_row(redis, "rubric_drafts", rid)
            if cached is not None and (active is None or cached.get("active") == active):
                cached_results[str(rid)] = GetRubricDraftResponse.model_validate(cached)
            else:
                missing_ids.append(rid)
    else:
        missing_ids = list(ids)

    if not missing_ids:
        return [cached_results[str(rid)] for rid in ids if str(rid) in cached_results]

    rows = await conn.fetch(
        """
        SELECT
            d.id, d.created_at, d.generated, d.mcp, d.active,
            d.session_id,
            d.name,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL AND dep.active = true), '{}') AS department_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL AND desc_c.active = true), '{}') AS description_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL AND f.active = true), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL AND n.active = true), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT pt.points_id) FILTER (WHERE pt.points_id IS NOT NULL AND pt.active = true), '{}') AS point_ids,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL), '{}') AS profile_ids,
            COALESCE(ARRAY_AGG(DISTINCT sg.standard_groups_id) FILTER (WHERE sg.standard_groups_id IS NOT NULL AND sg.active = true), '{}') AS standard_group_ids,
            COALESCE(ARRAY_AGG(DISTINCT s.standards_id) FILTER (WHERE s.standards_id IS NOT NULL AND s.active = true), '{}') AS standard_ids,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL AND dep.active = false), '{}') AS pending_department_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL AND desc_c.active = false), '{}') AS pending_description_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL AND f.active = false), '{}') AS pending_flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL AND n.active = false), '{}') AS pending_name_ids,
            COALESCE(ARRAY_AGG(DISTINCT pt.points_id) FILTER (WHERE pt.points_id IS NOT NULL AND pt.active = false), '{}') AS pending_point_ids,
            COALESCE(ARRAY_AGG(DISTINCT sg.standard_groups_id) FILTER (WHERE sg.standard_groups_id IS NOT NULL AND sg.active = false), '{}') AS pending_standard_group_ids,
            COALESCE(ARRAY_AGG(DISTINCT s.standards_id) FILTER (WHERE s.standards_id IS NOT NULL AND s.active = false), '{}') AS pending_standard_ids
        FROM rubric_drafts_entry d
        LEFT JOIN rubric_drafts_departments_connection dep ON dep.draft_id = d.id
        LEFT JOIN rubric_drafts_descriptions_connection desc_c ON desc_c.draft_id = d.id
        LEFT JOIN rubric_drafts_flags_connection f ON f.draft_id = d.id
        LEFT JOIN rubric_drafts_names_connection n ON n.draft_id = d.id
        LEFT JOIN rubric_drafts_points_connection pt ON pt.draft_id = d.id
        LEFT JOIN rubric_drafts_profiles_connection p ON p.draft_id = d.id
        LEFT JOIN rubric_drafts_standard_groups_connection sg ON sg.draft_id = d.id
        LEFT JOIN rubric_drafts_standards_connection s ON s.draft_id = d.id
        WHERE d.id = ANY($1)
          AND ($2::boolean IS NULL OR d.active = $2)
        GROUP BY d.id, d.created_at, d.generated, d.mcp, d.active,
                 d.session_id, d.name
        ORDER BY d.created_at DESC
        """,
        missing_ids,
        active,
    )

    mv_results: dict[str, GetRubricDraftResponse] = {}
    for r in rows:
        mv_results[str(r["id"])] = GetRubricDraftResponse(
            id=r["id"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
            active=r["active"],
            session_id=r["session_id"],
            name=r["name"],
            department_ids=r["department_ids"],
            description_ids=r["description_ids"],
            flag_ids=r["flag_ids"],
            name_ids=r["name_ids"],
            point_ids=r["point_ids"],
            profile_ids=r["profile_ids"],
            standard_group_ids=r["standard_group_ids"],
            standard_ids=r["standard_ids"],
            pending_department_ids=r["pending_department_ids"],
            pending_description_ids=r["pending_description_ids"],
            pending_flag_ids=r["pending_flag_ids"],
            pending_name_ids=r["pending_name_ids"],
            pending_point_ids=r["pending_point_ids"],
            pending_standard_group_ids=r["pending_standard_group_ids"],
            pending_standard_ids=r["pending_standard_ids"],
        )

    out: list[GetRubricDraftResponse] = []
    for rid in ids:
        key = str(rid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
