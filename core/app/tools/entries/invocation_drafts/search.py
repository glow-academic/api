"""Invocation drafts SEARCH — declarative filters on base table + connections."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.invocation_drafts.types import (
    GetInvocationDraftResponse,
)


async def search_invocation_drafts(
    conn: asyncpg.Connection,
    group_ids: list[UUID] | None = None,
    session_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    mcp: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[GetInvocationDraftResponse]:
    """Search invocation_drafts with declarative filters and connection data."""
    rows = await conn.fetch(
        """
        SELECT
            d.id, d.version, d.created_at, d.generated, d.mcp, d.active,
            d.group_id, d.session_id,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL), '{}') AS department_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL), '{}') AS description_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT k.keys_id) FILTER (WHERE k.keys_id IS NOT NULL), '{}') AS key_ids,
            COALESCE(ARRAY_AGG(DISTINCT mf.model_flags_id) FILTER (WHERE mf.model_flags_id IS NOT NULL), '{}') AS model_flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT mp.model_positions_id) FILTER (WHERE mp.model_positions_id IS NOT NULL), '{}') AS model_position_ids,
            COALESCE(ARRAY_AGG(DISTINCT mr.model_rubrics_id) FILTER (WHERE mr.model_rubrics_id IS NOT NULL), '{}') AS model_rubric_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL), '{}') AS profile_ids,
            COALESCE(ARRAY_AGG(DISTINCT rl.reasoning_levels_id) FILTER (WHERE rl.reasoning_levels_id IS NOT NULL), '{}') AS reasoning_level_ids,
            COALESCE(ARRAY_AGG(DISTINCT tl.temperature_levels_id) FILTER (WHERE tl.temperature_levels_id IS NOT NULL), '{}') AS temperature_level_ids,
            COALESCE(ARRAY_AGG(DISTINCT v.voices_id) FILTER (WHERE v.voices_id IS NOT NULL), '{}') AS voice_ids,
            COALESCE(ARRAY_AGG(DISTINCT val.values_id) FILTER (WHERE val.values_id IS NOT NULL), '{}') AS value_ids,
            COALESCE(ARRAY_AGG(DISTINCT pr.pricing_id) FILTER (WHERE pr.pricing_id IS NOT NULL), '{}') AS pricing_ids,
            COALESCE(ARRAY_AGG(DISTINCT ep.endpoints_id) FILTER (WHERE ep.endpoints_id IS NOT NULL), '{}') AS endpoint_ids
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
        GetInvocationDraftResponse(
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
            key_ids=r["key_ids"],
            model_flag_ids=r["model_flag_ids"],
            model_position_ids=r["model_position_ids"],
            model_rubric_ids=r["model_rubric_ids"],
            name_ids=r["name_ids"],
            profile_ids=r["profile_ids"],
            reasoning_level_ids=r["reasoning_level_ids"],
            temperature_level_ids=r["temperature_level_ids"],
            voice_ids=r["voice_ids"],
            value_ids=r["value_ids"],
            pricing_ids=r["pricing_ids"],
            endpoint_ids=r["endpoint_ids"],
        )
        for r in rows
    ]
