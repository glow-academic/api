"""Field drafts GET — read from base table + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.field_drafts.types import GetFieldDraftResponse


async def get_field_drafts(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    active: bool | None = True,
) -> list[GetFieldDraftResponse]:
    """Get field_drafts entries by IDs with connection data.

    ``active=True`` (default) — only returns committed drafts.
    ``active=False`` — only dormant pending drafts (rare).
    ``active=None`` — both. Use when loading a draft for the editor that
    may still be in pending state (soft_calls_entry ledger has it).
    """
    if not ids:
        return []

    rows = await conn.fetch(
        """
        SELECT
            d.id, d.created_at, d.generated, d.mcp, d.active,
            d.session_id,
            d.name,
            COALESCE(ARRAY_AGG(DISTINCT cp.conditional_parameters_id) FILTER (WHERE cp.conditional_parameters_id IS NOT NULL), '{}') AS conditional_parameter_ids,
            COALESCE(ARRAY_AGG(DISTINCT cp.conditional_parameters_id) FILTER (WHERE cp.conditional_parameters_id IS NOT NULL AND cp.active = false), '{}') AS pending_conditional_parameter_ids,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL), '{}') AS department_ids,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL AND dep.active = false), '{}') AS pending_department_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL), '{}') AS description_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL AND desc_c.active = false), '{}') AS pending_description_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL AND f.active = false), '{}') AS pending_flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL AND n.active = false), '{}') AS pending_name_ids,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL), '{}') AS profile_ids
        FROM field_drafts_entry d
        LEFT JOIN field_drafts_conditional_parameters_connection cp ON cp.draft_id = d.id
        LEFT JOIN field_drafts_departments_connection dep ON dep.draft_id = d.id
        LEFT JOIN field_drafts_descriptions_connection desc_c ON desc_c.draft_id = d.id
        LEFT JOIN field_drafts_flags_connection f ON f.draft_id = d.id
        LEFT JOIN field_drafts_names_connection n ON n.draft_id = d.id
        LEFT JOIN field_drafts_profiles_connection p ON p.draft_id = d.id
        WHERE d.id = ANY($1)
          AND ($2::boolean IS NULL OR d.active = $2)
        GROUP BY d.id, d.created_at, d.generated, d.mcp, d.active,
                 d.session_id, d.name
        ORDER BY d.created_at DESC
        """,
        ids,
        active,
    )

    return [
        GetFieldDraftResponse(
            id=r["id"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
            active=r["active"],
            session_id=r["session_id"],
            name=r["name"],
            conditional_parameter_ids=r["conditional_parameter_ids"],
            department_ids=r["department_ids"],
            description_ids=r["description_ids"],
            flag_ids=r["flag_ids"],
            name_ids=r["name_ids"],
            profile_ids=r["profile_ids"],
            pending_conditional_parameter_ids=r["pending_conditional_parameter_ids"],
            pending_department_ids=r["pending_department_ids"],
            pending_description_ids=r["pending_description_ids"],
            pending_flag_ids=r["pending_flag_ids"],
            pending_name_ids=r["pending_name_ids"],
        )
        for r in rows
    ]
