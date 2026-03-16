"""Agent drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.agent_drafts.types import CreateAgentDraftResponse


async def create_agent_draft(
    conn: asyncpg.Connection,
    group_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    version: int = 0,
    mcp: bool = False,
    soft: bool = False,
    name_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    model_ids: list[UUID] | None = None,
    tool_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    reasoning_level_ids: list[UUID] | None = None,
    temperature_level_ids: list[UUID] | None = None,
    voice_ids: list[UUID] | None = None,
    rubric_ids: list[UUID] | None = None,
) -> CreateAgentDraftResponse:
    """Create an agent_drafts entry with optional connection table links."""
    draft_id = await conn.fetchval(
        """
        INSERT INTO agent_drafts_entry (id, group_id, session_id, version, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id
        """,
        group_id,
        session_id,
        version,
        not soft,
        mcp,
        id,
    )

    if draft_id is None:
        raise ValueError("Failed to create agent_drafts entry")

    connections: list[tuple[str, str, list[UUID]]] = [
        ("agent_drafts_names_connection", "names_id", name_ids or []),
        (
            "agent_drafts_descriptions_connection",
            "descriptions_id",
            description_ids or [],
        ),
        ("agent_drafts_flags_connection", "flags_id", flag_ids or []),
        ("agent_drafts_departments_connection", "departments_id", department_ids or []),
        ("agent_drafts_models_connection", "models_id", model_ids or []),
        ("agent_drafts_tools_connection", "tools_id", tool_ids or []),
        ("agent_drafts_profiles_connection", "profiles_id", profile_ids or []),
        (
            "agent_drafts_reasoning_levels_connection",
            "reasoning_levels_id",
            reasoning_level_ids or [],
        ),
        (
            "agent_drafts_temperature_levels_connection",
            "temperature_levels_id",
            temperature_level_ids or [],
        ),
        ("agent_drafts_voices_connection", "voices_id", voice_ids or []),
        ("agent_drafts_rubrics_connection", "rubrics_id", rubric_ids or []),
    ]

    for table, col, ids in connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (draft_id, {col}) VALUES ($1, $2)",
                draft_id,
                rid,
            )

    return CreateAgentDraftResponse(id=draft_id)
