"""Department drafts GET — read from base table + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.department_drafts.types import (
    GetDepartmentDraftResponse,
)


async def get_department_drafts(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetDepartmentDraftResponse]:
    """Get department_drafts entries by IDs with connection data."""
    if not ids:
        return []

    rows = await conn.fetch(
        """
        SELECT
            d.id, d.version, d.created_at, d.generated, d.mcp, d.active,
            d.group_id, d.session_id,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL), '{}') AS description_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL), '{}') AS profile_ids,
            COALESCE(ARRAY_AGG(DISTINCT s.settings_id) FILTER (WHERE s.settings_id IS NOT NULL), '{}') AS setting_ids
        FROM department_drafts_entry d
        LEFT JOIN department_drafts_descriptions_connection desc_c ON desc_c.draft_id = d.id
        LEFT JOIN department_drafts_flags_connection f ON f.draft_id = d.id
        LEFT JOIN department_drafts_names_connection n ON n.draft_id = d.id
        LEFT JOIN department_drafts_profiles_connection p ON p.draft_id = d.id
        LEFT JOIN department_drafts_settings_connection s ON s.draft_id = d.id
        WHERE d.id = ANY($1)
          AND d.active = true
        GROUP BY d.id, d.version, d.created_at, d.generated, d.mcp, d.active,
                 d.group_id, d.session_id
        ORDER BY d.created_at DESC
        """,
        ids,
    )

    return [
        GetDepartmentDraftResponse(
            id=r["id"],
            version=r["version"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
            active=r["active"],
            group_id=r["group_id"],
            session_id=r["session_id"],
            description_ids=r["description_ids"],
            flag_ids=r["flag_ids"],
            name_ids=r["name_ids"],
            profile_ids=r["profile_ids"],
            setting_ids=r["setting_ids"],
        )
        for r in rows
    ]
