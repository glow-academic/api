"""Invocation drafts GET — read from base table + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.globals import get_redis_client
from app.tools.entries.invocation_drafts.types import (
    GetInvocationDraftResponse,
)
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_invocation_drafts(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetInvocationDraftResponse]:
    """Get invocation_drafts entries by IDs with connection data."""
    if not ids:
        return []

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
            COALESCE(ARRAY_AGG(DISTINCT mod.modalities_id) FILTER (WHERE mod.modalities_id IS NOT NULL), '{}') AS modality_ids,
            COALESCE(ARRAY_AGG(DISTINCT mod.modalities_id) FILTER (WHERE mod.modalities_id IS NOT NULL AND mod.active = false), '{}') AS pending_modality_ids,
            COALESCE(ARRAY_AGG(DISTINCT qual.qualities_id) FILTER (WHERE qual.qualities_id IS NOT NULL), '{}') AS quality_ids,
            COALESCE(ARRAY_AGG(DISTINCT qual.qualities_id) FILTER (WHERE qual.qualities_id IS NOT NULL AND qual.active = false), '{}') AS pending_quality_ids,
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
            COALESCE(ARRAY_AGG(DISTINCT ep.endpoints_id) FILTER (WHERE ep.endpoints_id IS NOT NULL), '{}') AS endpoint_ids
            ,COALESCE(ARRAY_AGG(DISTINCT ep.endpoints_id) FILTER (WHERE ep.endpoints_id IS NOT NULL AND ep.active = false), '{}') AS pending_endpoint_ids
        FROM invocation_drafts_entry d
        LEFT JOIN invocation_drafts_departments_connection dep ON dep.draft_id = d.id
        LEFT JOIN invocation_drafts_descriptions_connection desc_c ON desc_c.draft_id = d.id
        LEFT JOIN invocation_drafts_flags_connection f ON f.draft_id = d.id
        LEFT JOIN invocation_drafts_keys_connection k ON k.draft_id = d.id
        LEFT JOIN invocation_drafts_modalities_connection mod ON mod.draft_id = d.id
        LEFT JOIN invocation_drafts_qualities_connection qual ON qual.draft_id = d.id
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
        WHERE d.id = ANY($1)
          AND d.active = true
        GROUP BY d.id, d.created_at, d.generated, d.mcp, d.active,
                 d.session_id, d.name
        ORDER BY d.created_at DESC
        """,
        ids,
    )

    return [
        GetInvocationDraftResponse(
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
            key_ids=r["key_ids"],
            modality_ids=r["modality_ids"],
            quality_ids=r["quality_ids"],
            model_flag_ids=r["model_flag_ids"],
            model_position_ids=r["model_position_ids"],
            model_rubric_ids=r["model_rubric_ids"],
            name_ids=r["name_ids"],
            profile_ids=r["profile_ids"],
            reasoning_level_ids=r["reasoning_level_ids"],
            temperature_level_ids=r["temperature_level_ids"],
            voice_ids=r["voice_ids"],
            value_id=r["value_ids"][0] if r["value_ids"] else None,
            pricing_ids=r["pricing_ids"],
            endpoint_ids=r["endpoint_ids"],
            pending_department_ids=r["pending_department_ids"],
            pending_description_ids=r["pending_description_ids"],
            pending_flag_ids=r["pending_flag_ids"],
            pending_key_ids=r["pending_key_ids"],
            pending_modality_ids=r["pending_modality_ids"],
            pending_quality_ids=r["pending_quality_ids"],
            pending_model_flag_ids=r["pending_model_flag_ids"],
            pending_model_position_ids=r["pending_model_position_ids"],
            pending_model_rubric_ids=r["pending_model_rubric_ids"],
            pending_name_ids=r["pending_name_ids"],
            pending_reasoning_level_ids=r["pending_reasoning_level_ids"],
            pending_temperature_level_ids=r["pending_temperature_level_ids"],
            pending_voice_ids=r["pending_voice_ids"],
            pending_value_ids=r["pending_value_ids"],
            pending_pricing_ids=r["pending_pricing_ids"],
            pending_endpoint_ids=r["pending_endpoint_ids"],
        )
        for r in rows
    ]


async def get_invocation_drafts_entries_internal(
    pool_or_conn: asyncpg.Pool | asyncpg.Connection,
    ids: list[UUID],
    bypass_cache: bool = False,
) -> list[GetInvocationDraftResponse]:
    """Cached wrapper for get_invocation_drafts.

    Accepts either a Pool or a Connection — see get_names for rationale.
    """
    if not ids:
        return []

    tags = ["entries", "invocation_drafts"]
    cache_key_val = cache_key(
        "/entries/invocation_drafts/get",
        {"ids": [str(id) for id in ids]},
    )

    if not bypass_cache:
        cached = await get_cached(cache_key_val, redis=get_redis_client())
        if cached:
            return [
                GetInvocationDraftResponse.model_validate(i)
                for i in cached.get("items", [])
            ]

    if isinstance(pool_or_conn, asyncpg.Pool):
        async with pool_or_conn.acquire() as conn:
            items = await get_invocation_drafts(conn, ids)
    else:
        items = await get_invocation_drafts(pool_or_conn, ids)

    await set_cached(
        cache_key_val,
        {"items": [i.model_dump(mode="json") for i in items]},
        ttl=60,
        tags=tags,
        redis=get_redis_client(),
    )

    return items
