"""Setting drafts SEARCH — declarative filters on base table + connections."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.setting_drafts.types import GetSettingDraftResponse


async def search_setting_drafts(
    conn: asyncpg.Connection,
    group_ids: list[UUID] | None = None,
    session_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    mcp: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[GetSettingDraftResponse]:
    """Search setting_drafts with declarative filters and connection data."""
    rows = await conn.fetch(
        """
        SELECT
            d.id, d.version, d.created_at, d.generated, d.mcp, d.active,
            d.group_id, d.session_id,
            COALESCE(ARRAY_AGG(DISTINCT ag.agents_id) FILTER (WHERE ag.agents_id IS NOT NULL), '{}') AS agent_ids,
            COALESCE(ARRAY_AGG(DISTINCT aik.auth_item_keys_id) FILTER (WHERE aik.auth_item_keys_id IS NOT NULL), '{}') AS auth_item_key_ids,
            COALESCE(ARRAY_AGG(DISTINCT au.auths_id) FILTER (WHERE au.auths_id IS NOT NULL), '{}') AS auth_ids,
            COALESCE(ARRAY_AGG(DISTINCT c.colors_id) FILTER (WHERE c.colors_id IS NOT NULL), '{}') AS color_ids,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL), '{}') AS department_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL), '{}') AS description_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT it.items_id) FILTER (WHERE it.items_id IS NOT NULL), '{}') AS item_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL), '{}') AS profile_ids,
            COALESCE(ARRAY_AGG(DISTINCT pk.provider_keys_id) FILTER (WHERE pk.provider_keys_id IS NOT NULL), '{}') AS provider_key_ids,
            COALESCE(ARRAY_AGG(DISTINCT th.thresholds_id) FILTER (WHERE th.thresholds_id IS NOT NULL), '{}') AS threshold_ids
        FROM setting_drafts_entry d
        LEFT JOIN setting_drafts_agents_connection ag ON ag.draft_id = d.id
        LEFT JOIN setting_drafts_auth_item_keys_connection aik ON aik.draft_id = d.id
        LEFT JOIN setting_drafts_auths_connection au ON au.draft_id = d.id
        LEFT JOIN setting_drafts_colors_connection c ON c.draft_id = d.id
        LEFT JOIN setting_drafts_departments_connection dep ON dep.draft_id = d.id
        LEFT JOIN setting_drafts_descriptions_connection desc_c ON desc_c.draft_id = d.id
        LEFT JOIN setting_drafts_flags_connection f ON f.draft_id = d.id
        LEFT JOIN setting_drafts_items_connection it ON it.draft_id = d.id
        LEFT JOIN setting_drafts_names_connection n ON n.draft_id = d.id
        LEFT JOIN setting_drafts_profiles_connection p ON p.draft_id = d.id
        LEFT JOIN setting_drafts_provider_keys_connection pk ON pk.draft_id = d.id
        LEFT JOIN setting_drafts_thresholds_connection th ON th.draft_id = d.id
        WHERE d.active = true
          AND ($1::uuid[] IS NULL OR d.group_id = ANY($1))
          AND ($2::uuid[] IS NULL OR d.session_id = ANY($2))
          AND ($3::uuid[] IS NULL OR p.profiles_id = ANY($3))
          AND ($4::timestamptz IS NULL OR d.created_at >= $4)
          AND ($5::timestamptz IS NULL OR d.created_at <= $5)
          AND ($6::boolean IS NULL OR d.mcp = $6)
        GROUP BY d.id, d.version, d.created_at, d.generated, d.mcp, d.active,
                 d.group_id, d.session_id
        ORDER BY d.created_at DESC
        LIMIT $7 OFFSET $8
        """,
        group_ids,
        session_ids,
        profile_ids,
        date_from,
        date_to,
        mcp,
        limit,
        offset,
    )

    return [
        GetSettingDraftResponse(
            id=r["id"],
            version=r["version"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
            active=r["active"],
            group_id=r["group_id"],
            session_id=r["session_id"],
            agent_ids=r["agent_ids"],
            auth_item_key_ids=r["auth_item_key_ids"],
            auth_ids=r["auth_ids"],
            color_ids=r["color_ids"],
            department_ids=r["department_ids"],
            description_ids=r["description_ids"],
            flag_ids=r["flag_ids"],
            item_ids=r["item_ids"],
            name_ids=r["name_ids"],
            profile_ids=r["profile_ids"],
            provider_key_ids=r["provider_key_ids"],
            threshold_ids=r["threshold_ids"],
        )
        for r in rows
    ]
