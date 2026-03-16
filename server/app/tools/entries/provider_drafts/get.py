"""Provider drafts GET — read from base table + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.provider_drafts.types import GetProviderDraftResponse


async def get_provider_drafts(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetProviderDraftResponse]:
    """Get provider_drafts entries by IDs with connection data."""
    if not ids:
        return []

    rows = await conn.fetch(
        """
        SELECT
            d.id, d.version, d.created_at, d.generated, d.mcp, d.active,
            d.group_id, d.session_id,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL), '{}') AS department_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL), '{}') AS description_ids,
            COALESCE(ARRAY_AGG(DISTINCT e.endpoints_id) FILTER (WHERE e.endpoints_id IS NOT NULL), '{}') AS endpoint_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT k.keys_id) FILTER (WHERE k.keys_id IS NOT NULL), '{}') AS key_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL), '{}') AS profile_ids,
            COALESCE(ARRAY_AGG(DISTINCT v.values_id) FILTER (WHERE v.values_id IS NOT NULL), '{}') AS value_ids
        FROM provider_drafts_entry d
        LEFT JOIN provider_drafts_departments_connection dep ON dep.draft_id = d.id
        LEFT JOIN provider_drafts_descriptions_connection desc_c ON desc_c.draft_id = d.id
        LEFT JOIN provider_drafts_endpoints_connection e ON e.draft_id = d.id
        LEFT JOIN provider_drafts_flags_connection f ON f.draft_id = d.id
        LEFT JOIN provider_drafts_keys_connection k ON k.draft_id = d.id
        LEFT JOIN provider_drafts_names_connection n ON n.draft_id = d.id
        LEFT JOIN provider_drafts_profiles_connection p ON p.draft_id = d.id
        LEFT JOIN provider_drafts_values_connection v ON v.draft_id = d.id
        WHERE d.id = ANY($1)
          AND d.active = true
        GROUP BY d.id, d.version, d.created_at, d.generated, d.mcp, d.active,
                 d.group_id, d.session_id
        ORDER BY d.created_at DESC
        """,
        ids,
    )

    return [
        GetProviderDraftResponse(
            id=r["id"],
            version=r["version"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
            active=r["active"],
            group_id=r["group_id"],
            session_id=r["session_id"],
            department_ids=r["department_ids"],
            description_ids=r["description_ids"],
            endpoint_ids=r["endpoint_ids"],
            flag_ids=r["flag_ids"],
            key_ids=r["key_ids"],
            name_ids=r["name_ids"],
            profile_ids=r["profile_ids"],
            value_ids=r["value_ids"],
        )
        for r in rows
    ]
