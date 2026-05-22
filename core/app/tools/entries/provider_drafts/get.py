"""Provider drafts GET — read from base table + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.provider_drafts.types import GetProviderDraftResponse
from app.utils.cache.hedged_row import read_back_row


async def get_provider_drafts(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    active: bool | None = True,
    *,
    bypass_cache: bool = False,
) -> list[GetProviderDraftResponse]:
    """Get provider_drafts entries by IDs with connection data.

    ``active=None`` returns dormant + active rows.
    """
    if not ids:
        return []

    cached_results: dict[str, GetProviderDraftResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for rid in ids:
            cached = await read_back_row(redis, "provider_drafts", rid)
            if cached is not None and (active is None or cached.get("active") == active):
                cached_results[str(rid)] = GetProviderDraftResponse.model_validate(cached)
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
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL), '{}') AS department_ids,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL AND dep.active = false), '{}') AS pending_department_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL), '{}') AS description_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL AND desc_c.active = false), '{}') AS pending_description_ids,
            COALESCE(ARRAY_AGG(DISTINCT e.endpoints_id) FILTER (WHERE e.endpoints_id IS NOT NULL), '{}') AS endpoint_ids,
            COALESCE(ARRAY_AGG(DISTINCT e.endpoints_id) FILTER (WHERE e.endpoints_id IS NOT NULL AND e.active = false), '{}') AS pending_endpoint_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL AND f.active = false), '{}') AS pending_flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT k.keys_id) FILTER (WHERE k.keys_id IS NOT NULL), '{}') AS key_ids,
            COALESCE(ARRAY_AGG(DISTINCT k.keys_id) FILTER (WHERE k.keys_id IS NOT NULL AND k.active = false), '{}') AS pending_key_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL AND n.active = false), '{}') AS pending_name_ids,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL), '{}') AS profile_ids,
            COALESCE(ARRAY_AGG(DISTINCT v.values_id) FILTER (WHERE v.values_id IS NOT NULL), '{}') AS value_ids,
            COALESCE(ARRAY_AGG(DISTINCT v.values_id) FILTER (WHERE v.values_id IS NOT NULL AND v.active = false), '{}') AS pending_value_ids
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
          AND ($2::boolean IS NULL OR d.active = $2)
        GROUP BY d.id, d.created_at, d.generated, d.mcp, d.active,
                 d.session_id, d.name
        ORDER BY d.created_at DESC
        """,
        missing_ids,
        active,
    )

    mv_results: dict[str, GetProviderDraftResponse] = {}
    for r in rows:
        mv_results[str(r["id"])] = GetProviderDraftResponse(
            id=r["id"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
            active=r["active"],
            session_id=r["session_id"],
            name=r["name"],
            department_ids=r["department_ids"],
            description_ids=r["description_ids"],
            endpoint_ids=r["endpoint_ids"],
            flag_ids=r["flag_ids"],
            key_ids=r["key_ids"],
            name_ids=r["name_ids"],
            profile_ids=r["profile_ids"],
            value_id=r["value_ids"][0] if r["value_ids"] else None,
            pending_department_ids=r["pending_department_ids"],
            pending_description_ids=r["pending_description_ids"],
            pending_endpoint_ids=r["pending_endpoint_ids"],
            pending_flag_ids=r["pending_flag_ids"],
            pending_key_ids=r["pending_key_ids"],
            pending_name_ids=r["pending_name_ids"],
            pending_value_ids=r["pending_value_ids"],
        )

    out: list[GetProviderDraftResponse] = []
    for rid in ids:
        key = str(rid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
