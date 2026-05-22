"""Invocation drafts SEARCH — declarative filters on base table + connections."""

from datetime import datetime
from datetime import datetime as _dt
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.invocation_drafts.types import (
    GetInvocationDraftResponse,
)
from app.utils.cache.hedged_row import hedged_search


async def search_invocation_drafts(
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
) -> list[GetInvocationDraftResponse]:
    """Search invocation_drafts with declarative filters and connection data."""
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
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL AND f.active = false), '{}') AS pending_flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT k.keys_id) FILTER (WHERE k.keys_id IS NOT NULL), '{}') AS key_ids,
            COALESCE(ARRAY_AGG(DISTINCT k.keys_id) FILTER (WHERE k.keys_id IS NOT NULL AND k.active = false), '{}') AS pending_key_ids,
            COALESCE(ARRAY_AGG(DISTINCT mf.model_flags_id) FILTER (WHERE mf.model_flags_id IS NOT NULL), '{}') AS model_flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT mf.model_flags_id) FILTER (WHERE mf.model_flags_id IS NOT NULL AND mf.active = false), '{}') AS pending_model_flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT mp.model_positions_id) FILTER (WHERE mp.model_positions_id IS NOT NULL), '{}') AS model_position_ids,
            COALESCE(ARRAY_AGG(DISTINCT mp.model_positions_id) FILTER (WHERE mp.model_positions_id IS NOT NULL AND mp.active = false), '{}') AS pending_model_position_ids,
            COALESCE(ARRAY_AGG(DISTINCT mr.model_rubrics_id) FILTER (WHERE mr.model_rubrics_id IS NOT NULL), '{}') AS model_rubric_ids,
            COALESCE(ARRAY_AGG(DISTINCT mr.model_rubrics_id) FILTER (WHERE mr.model_rubrics_id IS NOT NULL AND mr.active = false), '{}') AS pending_model_rubric_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL AND n.active = false), '{}') AS pending_name_ids,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL), '{}') AS profile_ids,
            COALESCE(ARRAY_AGG(DISTINCT rl.reasoning_levels_id) FILTER (WHERE rl.reasoning_levels_id IS NOT NULL), '{}') AS reasoning_level_ids,
            COALESCE(ARRAY_AGG(DISTINCT rl.reasoning_levels_id) FILTER (WHERE rl.reasoning_levels_id IS NOT NULL AND rl.active = false), '{}') AS pending_reasoning_level_ids,
            COALESCE(ARRAY_AGG(DISTINCT tl.temperature_levels_id) FILTER (WHERE tl.temperature_levels_id IS NOT NULL), '{}') AS temperature_level_ids,
            COALESCE(ARRAY_AGG(DISTINCT tl.temperature_levels_id) FILTER (WHERE tl.temperature_levels_id IS NOT NULL AND tl.active = false), '{}') AS pending_temperature_level_ids,
            COALESCE(ARRAY_AGG(DISTINCT v.voices_id) FILTER (WHERE v.voices_id IS NOT NULL), '{}') AS voice_ids,
            COALESCE(ARRAY_AGG(DISTINCT v.voices_id) FILTER (WHERE v.voices_id IS NOT NULL AND v.active = false), '{}') AS pending_voice_ids,
            COALESCE(ARRAY_AGG(DISTINCT val.values_id) FILTER (WHERE val.values_id IS NOT NULL), '{}') AS value_ids,
            COALESCE(ARRAY_AGG(DISTINCT val.values_id) FILTER (WHERE val.values_id IS NOT NULL AND val.active = false), '{}') AS pending_value_ids,
            COALESCE(ARRAY_AGG(DISTINCT pr.pricing_id) FILTER (WHERE pr.pricing_id IS NOT NULL), '{}') AS pricing_ids,
            COALESCE(ARRAY_AGG(DISTINCT pr.pricing_id) FILTER (WHERE pr.pricing_id IS NOT NULL AND pr.active = false), '{}') AS pending_pricing_ids,
            COALESCE(ARRAY_AGG(DISTINCT ep.endpoints_id) FILTER (WHERE ep.endpoints_id IS NOT NULL), '{}') AS endpoint_ids,
            COALESCE(ARRAY_AGG(DISTINCT ep.endpoints_id) FILTER (WHERE ep.endpoints_id IS NOT NULL AND ep.active = false), '{}') AS pending_endpoint_ids
        FROM invocation_drafts_entry d
        LEFT JOIN invocation_drafts_departments_connection dep ON dep.draft_id = d.id
        LEFT JOIN invocation_drafts_descriptions_connection desc_c ON desc_c.draft_id = d.id
        LEFT JOIN invocation_drafts_flags_connection f ON f.draft_id = d.id
        LEFT JOIN invocation_drafts_keys_connection k ON k.draft_id = d.id
        LEFT JOIN invocation_drafts_model_flags_connection mf ON mf.draft_id = d.id
        LEFT JOIN invocation_drafts_model_positions_connection mp ON mp.draft_id = d.id
        LEFT JOIN invocation_drafts_model_rubrics_connection mr ON mr.draft_id = d.id
        LEFT JOIN invocation_drafts_names_connection n ON n.draft_id = d.id
        LEFT JOIN invocation_drafts_profiles_connection p ON p.draft_id = d.id
        LEFT JOIN invocation_drafts_reasoning_levels_connection rl ON rl.draft_id = d.id
        LEFT JOIN invocation_drafts_temperature_levels_connection tl ON tl.draft_id = d.id
        LEFT JOIN invocation_drafts_voices_connection v ON v.draft_id = d.id
        LEFT JOIN invocation_drafts_values_connection val ON val.invocation_drafts_id = d.id
        LEFT JOIN invocation_drafts_pricing_connection pr ON pr.invocation_drafts_id = d.id
        LEFT JOIN invocation_drafts_endpoints_connection ep ON ep.invocation_drafts_id = d.id
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
            "key_ids": _strs(r["key_ids"]),
            "modality_ids": [],
            "quality_ids": [],
            "model_flag_ids": _strs(r["model_flag_ids"]),
            "model_position_ids": _strs(r["model_position_ids"]),
            "model_rubric_ids": _strs(r["model_rubric_ids"]),
            "name_ids": _strs(r["name_ids"]),
            "profile_ids": _strs(r["profile_ids"]),
            "reasoning_level_ids": _strs(r["reasoning_level_ids"]),
            "temperature_level_ids": _strs(r["temperature_level_ids"]),
            "voice_ids": _strs(r["voice_ids"]),
            "value_id": str(r["value_ids"][0]) if r["value_ids"] else None,
            "pricing_ids": _strs(r["pricing_ids"]),
            "endpoint_ids": _strs(r["endpoint_ids"]),
            "pending_department_ids": _strs(r["pending_department_ids"]),
            "pending_description_ids": _strs(r["pending_description_ids"]),
            "pending_flag_ids": _strs(r["pending_flag_ids"]),
            "pending_key_ids": _strs(r["pending_key_ids"]),
            "pending_modality_ids": [],
            "pending_quality_ids": [],
            "pending_model_flag_ids": _strs(r["pending_model_flag_ids"]),
            "pending_model_position_ids": _strs(r["pending_model_position_ids"]),
            "pending_model_rubric_ids": _strs(r["pending_model_rubric_ids"]),
            "pending_name_ids": _strs(r["pending_name_ids"]),
            "pending_reasoning_level_ids": _strs(r["pending_reasoning_level_ids"]),
            "pending_temperature_level_ids": _strs(r["pending_temperature_level_ids"]),
            "pending_voice_ids": _strs(r["pending_voice_ids"]),
            "pending_value_ids": _strs(r["pending_value_ids"]),
            "pending_pricing_ids": _strs(r["pending_pricing_ids"]),
            "pending_endpoint_ids": _strs(r["pending_endpoint_ids"]),
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
        "invocation_drafts",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetInvocationDraftResponse.model_validate(r) for r in merged]
