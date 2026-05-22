"""Model drafts SEARCH — declarative filters on base table + connections."""

from datetime import datetime
from datetime import datetime as _dt
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.model_drafts.types import GetModelDraftResponse
from app.utils.cache.hedged_row import hedged_search


async def search_model_drafts(
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
    bypass_cache: bool = False,
) -> list[GetModelDraftResponse]:
    """Search model_drafts with declarative filters and connection data."""
    rows = await conn.fetch(
        """
        SELECT
            d.id, d.created_at, d.generated, d.mcp, d.active,
            d.session_id,
            d.name,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL), '{}') AS department_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL), '{}') AS description_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT mod.modalities_id) FILTER (WHERE mod.modalities_id IS NOT NULL), '{}') AS modality_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT pr.pricing_id) FILTER (WHERE pr.pricing_id IS NOT NULL), '{}') AS pricing_ids,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL), '{}') AS profile_ids,
            COALESCE(ARRAY_AGG(DISTINCT prov.providers_id) FILTER (WHERE prov.providers_id IS NOT NULL), '{}') AS provider_ids,
            COALESCE(ARRAY_AGG(DISTINCT q.qualities_id) FILTER (WHERE q.qualities_id IS NOT NULL), '{}') AS quality_ids,
            COALESCE(ARRAY_AGG(DISTINCT rl.reasoning_levels_id) FILTER (WHERE rl.reasoning_levels_id IS NOT NULL), '{}') AS reasoning_level_ids,
            COALESCE(ARRAY_AGG(DISTINCT tl.temperature_levels_id) FILTER (WHERE tl.temperature_levels_id IS NOT NULL), '{}') AS temperature_level_ids,
            COALESCE(ARRAY_AGG(DISTINCT val.values_id) FILTER (WHERE val.values_id IS NOT NULL), '{}') AS value_ids,
            COALESCE(ARRAY_AGG(DISTINCT v.voices_id) FILTER (WHERE v.voices_id IS NOT NULL), '{}') AS voice_ids
        FROM model_drafts_entry d
        LEFT JOIN model_drafts_departments_connection dep ON dep.draft_id = d.id
        LEFT JOIN model_drafts_descriptions_connection desc_c ON desc_c.draft_id = d.id
        LEFT JOIN model_drafts_flags_connection f ON f.draft_id = d.id
        LEFT JOIN model_drafts_modalities_connection mod ON mod.draft_id = d.id
        LEFT JOIN model_drafts_names_connection n ON n.draft_id = d.id
        LEFT JOIN model_drafts_pricing_connection pr ON pr.draft_id = d.id
        LEFT JOIN model_drafts_profiles_connection p ON p.draft_id = d.id
        LEFT JOIN model_drafts_providers_connection prov ON prov.draft_id = d.id
        LEFT JOIN model_drafts_qualities_connection q ON q.draft_id = d.id
        LEFT JOIN model_drafts_reasoning_levels_connection rl ON rl.draft_id = d.id
        LEFT JOIN model_drafts_temperature_levels_connection tl ON tl.draft_id = d.id
        LEFT JOIN model_drafts_values_connection val ON val.draft_id = d.id
        LEFT JOIN model_drafts_voices_connection v ON v.draft_id = d.id
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
        limit + offset + 1000,
        0,
    )

    def _strs(v):
        return [str(x) for x in (v or [])]

    mv_dicts: list[dict] = [
        {
            "id": str(r["id"]),
            "created_at": r["created_at"],
            "generated": r["generated"],
            "mcp": r["mcp"],
            "active": r["active"],
            "session_id": str(r["session_id"]) if r["session_id"] else None,
            "name": r["name"],
            "department_ids": _strs(r["department_ids"]),
            "description_ids": _strs(r["description_ids"]),
            "flag_ids": _strs(r["flag_ids"]),
            "modality_ids": _strs(r["modality_ids"]),
            "name_ids": _strs(r["name_ids"]),
            "pricing_ids": _strs(r["pricing_ids"]),
            "profile_ids": _strs(r["profile_ids"]),
            "provider_ids": _strs(r["provider_ids"]),
            "quality_ids": _strs(r["quality_ids"]),
            "reasoning_level_ids": _strs(r["reasoning_level_ids"]),
            "temperature_level_ids": _strs(r["temperature_level_ids"]),
            "value_id": str(r["value_ids"][0]) if r["value_ids"] else None,
            "voice_ids": _strs(r["voice_ids"]),
            "pending_department_ids": [],
            "pending_description_ids": [],
            "pending_flag_ids": [],
            "pending_modality_ids": [],
            "pending_name_ids": [],
            "pending_pricing_ids": [],
            "pending_provider_ids": [],
            "pending_quality_ids": [],
            "pending_reasoning_level_ids": [],
            "pending_temperature_level_ids": [],
            "pending_value_ids": [],
            "pending_voice_ids": [],
        }
        for r in rows
    ]

    session_ids_str = {str(x) for x in session_ids} if session_ids else None
    profile_ids_str = {str(x) for x in profile_ids} if profile_ids else None

    def _parse_ts(ts):
        if isinstance(ts, str):
            return _dt.fromisoformat(ts)
        return ts

    name_lc = name.lower() if name else None

    def matches(row: dict) -> bool:
        if not row.get("active"):
            return False
        if session_ids_str is not None and str(row.get("session_id")) not in session_ids_str:
            return False
        if profile_ids_str is not None:
            row_profiles = {str(x) for x in (row.get("profile_ids") or [])}
            if not (row_profiles & profile_ids_str):
                return False
        ts = _parse_ts(row.get("created_at"))
        if date_from is not None and (ts is None or ts < date_from):
            return False
        if date_to is not None and (ts is None or ts > date_to):
            return False
        if mcp is not None and row.get("mcp") != mcp:
            return False
        if name_lc is not None:
            row_name = (row.get("name") or "").lower()
            if name_lc not in row_name:
                return False
        return True

    merged = await hedged_search(
        redis,
        "model_drafts",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetModelDraftResponse.model_validate(r) for r in merged]
