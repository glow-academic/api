"""Agent drafts SEARCH — declarative filters on base table + connections."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.agent_drafts.types import GetAgentDraftResponse


async def search_agent_drafts(
    conn: asyncpg.Connection,
    group_ids: list[UUID] | None = None,
    session_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    mcp: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[GetAgentDraftResponse]:
    """Search agent_drafts with declarative filters and connection data."""
    rows = await conn.fetch(
        """
        SELECT
            d.id, d.version, d.created_at, d.generated, d.mcp, d.active,
            d.group_id, d.session_id,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL), '{}') AS description_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL), '{}') AS department_ids,
            COALESCE(ARRAY_AGG(DISTINCT m.models_id) FILTER (WHERE m.models_id IS NOT NULL), '{}') AS model_ids,
            COALESCE(ARRAY_AGG(DISTINCT t.tools_id) FILTER (WHERE t.tools_id IS NOT NULL), '{}') AS tool_ids,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL), '{}') AS profile_ids,
            COALESCE(ARRAY_AGG(DISTINCT q.qualities_id) FILTER (WHERE q.qualities_id IS NOT NULL), '{}') AS quality_ids,
            COALESCE(ARRAY_AGG(DISTINCT rl.reasoning_levels_id) FILTER (WHERE rl.reasoning_levels_id IS NOT NULL), '{}') AS reasoning_level_ids,
            COALESCE(ARRAY_AGG(DISTINCT tl.temperature_levels_id) FILTER (WHERE tl.temperature_levels_id IS NOT NULL), '{}') AS temperature_level_ids,
            COALESCE(ARRAY_AGG(DISTINCT v.voices_id) FILTER (WHERE v.voices_id IS NOT NULL), '{}') AS voice_ids,
            COALESCE(ARRAY_AGG(DISTINCT rb.rubrics_id) FILTER (WHERE rb.rubrics_id IS NOT NULL), '{}') AS rubric_ids
        FROM agent_drafts_entry d
        LEFT JOIN agent_drafts_names_connection n ON n.draft_id = d.id
        LEFT JOIN agent_drafts_descriptions_connection desc_c ON desc_c.draft_id = d.id
        LEFT JOIN agent_drafts_flags_connection f ON f.draft_id = d.id
        LEFT JOIN agent_drafts_departments_connection dep ON dep.draft_id = d.id
        LEFT JOIN agent_drafts_models_connection m ON m.draft_id = d.id
        LEFT JOIN agent_drafts_tools_connection t ON t.draft_id = d.id
        LEFT JOIN agent_drafts_profiles_connection p ON p.draft_id = d.id
        LEFT JOIN agent_drafts_qualities_connection q ON q.draft_id = d.id
        LEFT JOIN agent_drafts_reasoning_levels_connection rl ON rl.draft_id = d.id
        LEFT JOIN agent_drafts_temperature_levels_connection tl ON tl.draft_id = d.id
        LEFT JOIN agent_drafts_voices_connection v ON v.draft_id = d.id
        LEFT JOIN agent_drafts_rubrics_connection rb ON rb.draft_id = d.id
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
        GetAgentDraftResponse(
            id=r["id"],
            version=r["version"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
            active=r["active"],
            group_id=r["group_id"],
            session_id=r["session_id"],
            name_ids=r["name_ids"],
            description_ids=r["description_ids"],
            flag_ids=r["flag_ids"],
            department_ids=r["department_ids"],
            model_ids=r["model_ids"],
            tool_ids=r["tool_ids"],
            profile_ids=r["profile_ids"],
            quality_ids=r["quality_ids"],
            reasoning_level_ids=r["reasoning_level_ids"],
            temperature_level_ids=r["temperature_level_ids"],
            voice_ids=r["voice_ids"],
            rubric_ids=r["rubric_ids"],
        )
        for r in rows
    ]
