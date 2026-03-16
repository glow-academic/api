"""Model drafts GET — read from base table + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.model_drafts.types import GetModelDraftResponse


async def get_model_drafts(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetModelDraftResponse]:
    """Get model_drafts entries by IDs with connection data."""
    if not ids:
        return []

    rows = await conn.fetch(
        """
        SELECT
            d.id, d.version, d.created_at, d.generated, d.mcp, d.active,
            d.group_id, d.session_id,
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
        WHERE d.id = ANY($1)
          AND d.active = true
        GROUP BY d.id, d.version, d.created_at, d.generated, d.mcp, d.active,
                 d.group_id, d.session_id
        ORDER BY d.created_at DESC
        """,
        ids,
    )

    return [
        GetModelDraftResponse(
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
            flag_ids=r["flag_ids"],
            modality_ids=r["modality_ids"],
            name_ids=r["name_ids"],
            pricing_ids=r["pricing_ids"],
            profile_ids=r["profile_ids"],
            provider_ids=r["provider_ids"],
            quality_ids=r["quality_ids"],
            reasoning_level_ids=r["reasoning_level_ids"],
            temperature_level_ids=r["temperature_level_ids"],
            value_ids=r["value_ids"],
            voice_ids=r["voice_ids"],
        )
        for r in rows
    ]
