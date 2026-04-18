"""Agent drafts GET — read from base table + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.agent_drafts.types import GetAgentDraftResponse


async def get_agent_drafts(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetAgentDraftResponse]:
    """Get agent_drafts entries by IDs with connection data."""
    if not ids:
        return []

    rows = await conn.fetch(
        """
        SELECT
            d.id, d.created_at, d.generated, d.mcp, d.active,
            d.session_id,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL AND n.active = false), '{}') AS pending_name_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL), '{}') AS description_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL AND desc_c.active = false), '{}') AS pending_description_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL AND f.active = false), '{}') AS pending_flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL), '{}') AS department_ids,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL AND dep.active = false), '{}') AS pending_department_ids,
            COALESCE(ARRAY_AGG(DISTINCT m.models_id) FILTER (WHERE m.models_id IS NOT NULL), '{}') AS model_ids,
            COALESCE(ARRAY_AGG(DISTINCT m.models_id) FILTER (WHERE m.models_id IS NOT NULL AND m.active = false), '{}') AS pending_model_ids,
            COALESCE(ARRAY_AGG(DISTINCT t.tools_id) FILTER (WHERE t.tools_id IS NOT NULL), '{}') AS tool_ids,
            COALESCE(ARRAY_AGG(DISTINCT t.tools_id) FILTER (WHERE t.tools_id IS NOT NULL AND t.active = false), '{}') AS pending_tool_ids,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL), '{}') AS profile_ids,
            COALESCE(ARRAY_AGG(DISTINCT rl.reasoning_levels_id) FILTER (WHERE rl.reasoning_levels_id IS NOT NULL), '{}') AS reasoning_level_ids,
            COALESCE(ARRAY_AGG(DISTINCT rl.reasoning_levels_id) FILTER (WHERE rl.reasoning_levels_id IS NOT NULL AND rl.active = false), '{}') AS pending_reasoning_level_ids,
            COALESCE(ARRAY_AGG(DISTINCT tl.temperature_levels_id) FILTER (WHERE tl.temperature_levels_id IS NOT NULL), '{}') AS temperature_level_ids,
            COALESCE(ARRAY_AGG(DISTINCT tl.temperature_levels_id) FILTER (WHERE tl.temperature_levels_id IS NOT NULL AND tl.active = false), '{}') AS pending_temperature_level_ids,
            COALESCE(ARRAY_AGG(DISTINCT v.voices_id) FILTER (WHERE v.voices_id IS NOT NULL), '{}') AS voice_ids,
            COALESCE(ARRAY_AGG(DISTINCT v.voices_id) FILTER (WHERE v.voices_id IS NOT NULL AND v.active = false), '{}') AS pending_voice_ids,
            COALESCE(ARRAY_AGG(DISTINCT q.qualities_id) FILTER (WHERE q.qualities_id IS NOT NULL), '{}') AS quality_ids,
            COALESCE(ARRAY_AGG(DISTINCT q.qualities_id) FILTER (WHERE q.qualities_id IS NOT NULL AND q.active = false), '{}') AS pending_quality_ids,
            COALESCE(ARRAY_AGG(DISTINCT rb.rubrics_id) FILTER (WHERE rb.rubrics_id IS NOT NULL), '{}') AS rubric_ids,
            COALESCE(ARRAY_AGG(DISTINCT rb.rubrics_id) FILTER (WHERE rb.rubrics_id IS NOT NULL AND rb.active = false), '{}') AS pending_rubric_ids,
            COALESCE(ARRAY_AGG(DISTINCT pr.prompts_id) FILTER (WHERE pr.prompts_id IS NOT NULL), '{}') AS prompt_ids,
            COALESCE(ARRAY_AGG(DISTINCT pr.prompts_id) FILTER (WHERE pr.prompts_id IS NOT NULL AND pr.active = false), '{}') AS pending_prompt_ids,
            COALESCE(ARRAY_AGG(DISTINCT ins.instructions_id) FILTER (WHERE ins.instructions_id IS NOT NULL), '{}') AS instruction_ids,
            COALESCE(ARRAY_AGG(DISTINCT ins.instructions_id) FILTER (WHERE ins.instructions_id IS NOT NULL AND ins.active = false), '{}') AS pending_instruction_ids,
            COALESCE(ARRAY_AGG(DISTINCT ag.agents_id) FILTER (WHERE ag.agents_id IS NOT NULL), '{}') AS agent_ids,
            COALESCE(ARRAY_AGG(DISTINCT ag.agents_id) FILTER (WHERE ag.agents_id IS NOT NULL AND ag.active = false), '{}') AS pending_agent_ids
        FROM agent_drafts_entry d
        LEFT JOIN agent_drafts_names_connection n ON n.draft_id = d.id
        LEFT JOIN agent_drafts_descriptions_connection desc_c ON desc_c.draft_id = d.id
        LEFT JOIN agent_drafts_flags_connection f ON f.draft_id = d.id
        LEFT JOIN agent_drafts_departments_connection dep ON dep.draft_id = d.id
        LEFT JOIN agent_drafts_models_connection m ON m.draft_id = d.id
        LEFT JOIN agent_drafts_tools_connection t ON t.draft_id = d.id
        LEFT JOIN agent_drafts_profiles_connection p ON p.draft_id = d.id
        LEFT JOIN agent_drafts_reasoning_levels_connection rl ON rl.draft_id = d.id
        LEFT JOIN agent_drafts_temperature_levels_connection tl ON tl.draft_id = d.id
        LEFT JOIN agent_drafts_voices_connection v ON v.draft_id = d.id
        LEFT JOIN agent_drafts_qualities_connection q ON q.draft_id = d.id
        LEFT JOIN agent_drafts_rubrics_connection rb ON rb.draft_id = d.id
        LEFT JOIN agent_drafts_prompts_connection pr ON pr.draft_id = d.id
        LEFT JOIN agent_drafts_instructions_connection ins ON ins.draft_id = d.id
        LEFT JOIN agent_drafts_agents_connection ag ON ag.draft_id = d.id
        WHERE d.id = ANY($1)
          AND d.active = true
        GROUP BY d.id, d.created_at, d.generated, d.mcp, d.active,
                 d.session_id
        ORDER BY d.created_at DESC
        """,
        ids,
    )

    return [
        GetAgentDraftResponse(
            id=r["id"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
            active=r["active"],
            session_id=r["session_id"],
            name_ids=r["name_ids"],
            description_ids=r["description_ids"],
            flag_ids=r["flag_ids"],
            department_ids=r["department_ids"],
            model_ids=r["model_ids"],
            tool_ids=r["tool_ids"],
            profile_ids=r["profile_ids"],
            reasoning_level_ids=r["reasoning_level_ids"],
            temperature_level_ids=r["temperature_level_ids"],
            voice_ids=r["voice_ids"],
            quality_ids=r["quality_ids"],
            rubric_ids=r["rubric_ids"],
            prompt_ids=r["prompt_ids"],
            instruction_ids=r["instruction_ids"],
            agent_ids=r["agent_ids"],
            pending_name_ids=r["pending_name_ids"],
            pending_description_ids=r["pending_description_ids"],
            pending_flag_ids=r["pending_flag_ids"],
            pending_department_ids=r["pending_department_ids"],
            pending_model_ids=r["pending_model_ids"],
            pending_tool_ids=r["pending_tool_ids"],
            pending_reasoning_level_ids=r["pending_reasoning_level_ids"],
            pending_temperature_level_ids=r["pending_temperature_level_ids"],
            pending_voice_ids=r["pending_voice_ids"],
            pending_quality_ids=r["pending_quality_ids"],
            pending_rubric_ids=r["pending_rubric_ids"],
            pending_prompt_ids=r["pending_prompt_ids"],
            pending_instruction_ids=r["pending_instruction_ids"],
            pending_agent_ids=r["pending_agent_ids"],
        )
        for r in rows
    ]
