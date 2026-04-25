"""Setting drafts SEARCH — declarative filters on base table + connections."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.setting_drafts.types import GetSettingDraftResponse


async def search_setting_drafts(
    conn: asyncpg.Connection,
    session_ids: list[UUID] | None = None,
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
            d.id, d.created_at, d.generated, d.mcp, d.active,
            d.session_id,
            COALESCE(ARRAY_AGG(DISTINCT ag.agents_id) FILTER (WHERE ag.agents_id IS NOT NULL), '{}') AS agent_ids,
            COALESCE(ARRAY_AGG(DISTINCT ag.agents_id) FILTER (WHERE ag.agents_id IS NOT NULL AND ag.active = false), '{}') AS pending_agent_ids,
            COALESCE(ARRAY_AGG(DISTINCT aik.auth_item_keys_id) FILTER (WHERE aik.auth_item_keys_id IS NOT NULL), '{}') AS auth_item_key_ids,
            COALESCE(ARRAY_AGG(DISTINCT aik.auth_item_keys_id) FILTER (WHERE aik.auth_item_keys_id IS NOT NULL AND aik.active = false), '{}') AS pending_auth_item_key_ids,
            COALESCE(ARRAY_AGG(DISTINCT au.auths_id) FILTER (WHERE au.auths_id IS NOT NULL), '{}') AS auth_ids,
            COALESCE(ARRAY_AGG(DISTINCT au.auths_id) FILTER (WHERE au.auths_id IS NOT NULL AND au.active = false), '{}') AS pending_auth_ids,
            COALESCE(ARRAY_AGG(DISTINCT c.colors_id) FILTER (WHERE c.colors_id IS NOT NULL), '{}') AS color_ids,
            COALESCE(ARRAY_AGG(DISTINCT c.colors_id) FILTER (WHERE c.colors_id IS NOT NULL AND c.active = false), '{}') AS pending_color_ids,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL), '{}') AS department_ids,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL AND dep.active = false), '{}') AS pending_department_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL), '{}') AS description_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL AND desc_c.active = false), '{}') AS pending_description_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL AND f.active = false), '{}') AS pending_flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT it.items_id) FILTER (WHERE it.items_id IS NOT NULL), '{}') AS item_ids,
            COALESCE(ARRAY_AGG(DISTINCT it.items_id) FILTER (WHERE it.items_id IS NOT NULL AND it.active = false), '{}') AS pending_item_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL AND n.active = false), '{}') AS pending_name_ids,
            COALESCE(ARRAY_AGG(DISTINCT pv.providers_id) FILTER (WHERE pv.providers_id IS NOT NULL), '{}') AS provider_ids,
            COALESCE(ARRAY_AGG(DISTINCT pv.providers_id) FILTER (WHERE pv.providers_id IS NOT NULL AND pv.active = false), '{}') AS pending_provider_ids,
            COALESCE(ARRAY_AGG(DISTINCT pk.provider_keys_id) FILTER (WHERE pk.provider_keys_id IS NOT NULL), '{}') AS provider_key_ids,
            COALESCE(ARRAY_AGG(DISTINCT pk.provider_keys_id) FILTER (WHERE pk.provider_keys_id IS NOT NULL AND pk.active = false), '{}') AS pending_provider_key_ids,
            COALESCE(ARRAY_AGG(DISTINCT th.thresholds_id) FILTER (WHERE th.thresholds_id IS NOT NULL), '{}') AS threshold_ids
            ,
            COALESCE(ARRAY_AGG(DISTINCT th.thresholds_id) FILTER (WHERE th.thresholds_id IS NOT NULL AND th.active = false), '{}') AS pending_threshold_ids
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
        LEFT JOIN setting_drafts_providers_connection pv ON pv.draft_id = d.id
        LEFT JOIN setting_drafts_provider_keys_connection pk ON pk.draft_id = d.id
        LEFT JOIN setting_drafts_thresholds_connection th ON th.draft_id = d.id
        WHERE d.active = true
          AND ($1::uuid[] IS NULL OR d.session_id = ANY($1))
          AND ($2::timestamptz IS NULL OR d.created_at >= $2)
          AND ($3::timestamptz IS NULL OR d.created_at <= $3)
          AND ($4::boolean IS NULL OR d.mcp = $4)
        GROUP BY d.id, d.created_at, d.generated, d.mcp, d.active,
                 d.session_id
        ORDER BY d.created_at DESC
        LIMIT $5 OFFSET $6
        """,
        session_ids,
        date_from,
        date_to,
        mcp,
        limit,
        offset,
    )

    return [
        GetSettingDraftResponse(
            id=r["id"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
            active=r["active"],
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
            provider_ids=r["provider_ids"],
            provider_key_ids=r["provider_key_ids"],
            threshold_ids=r["threshold_ids"],
            pending_agent_ids=r["pending_agent_ids"],
            pending_auth_item_key_ids=r["pending_auth_item_key_ids"],
            pending_auth_ids=r["pending_auth_ids"],
            pending_color_ids=r["pending_color_ids"],
            pending_department_ids=r["pending_department_ids"],
            pending_description_ids=r["pending_description_ids"],
            pending_flag_ids=r["pending_flag_ids"],
            pending_item_ids=r["pending_item_ids"],
            pending_name_ids=r["pending_name_ids"],
            pending_provider_ids=r["pending_provider_ids"],
            pending_provider_key_ids=r["pending_provider_key_ids"],
            pending_threshold_ids=r["pending_threshold_ids"],
        )
        for r in rows
    ]
