"""Rubric drafts SEARCH — declarative filters on base table + connections."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.rubric_drafts.types import GetRubricDraftResponse


async def search_rubric_drafts(
    conn: asyncpg.Connection,
    redis: Redis,
    session_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    name: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    mcp: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[GetRubricDraftResponse]:
    """Search rubric_drafts with declarative filters and connection data."""
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
        WHERE d.active = true
          AND ($1::uuid[] IS NULL OR d.session_id = ANY($1))
          AND ($2::uuid[] IS NULL OR p.profiles_id = ANY($2))
          AND ($3::timestamptz IS NULL OR d.created_at >= $3)
          AND ($4::timestamptz IS NULL OR d.created_at <= $4)
          AND ($5::boolean IS NULL OR d.mcp = $5)
          AND ($6::text IS NULL OR d.name ILIKE '%' || $6 || '%')
        GROUP BY d.id, d.created_at, d.generated, d.mcp, d.active,
                 d.session_id, d.name
        ORDER BY d.created_at DESC
        LIMIT $7 OFFSET $8
        """,
        session_ids,
        profile_ids,
        date_from,
        date_to,
        mcp,
        name,
        limit,
        offset,
    )

    return [
        GetRubricDraftResponse(
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
        for r in rows
    ]
