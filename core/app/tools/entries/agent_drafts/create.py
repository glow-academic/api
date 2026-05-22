"""Agent drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.agent_drafts.types import CreateAgentDraftResponse
from app.utils.cache.hedged_row import write_back_row


async def create_agent_draft(
    conn: asyncpg.Connection,
    redis: Redis,
    session_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    name: str = "",
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
    quality_ids: list[UUID] | None = None,
    rubric_ids: list[UUID] | None = None,
    prompt_ids: list[UUID] | None = None,
    instruction_ids: list[UUID] | None = None,
    agent_ids: list[UUID] | None = None,
    pending_ids: set[UUID] | None = None,
) -> CreateAgentDraftResponse:
    """Create an agent_drafts entry with optional connection table links."""
    row = await conn.fetchrow(
        """
        INSERT INTO agent_drafts_entry (id, session_id, active, mcp, generated, name)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, true, $4)
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id, created_at, active
        """,
        session_id,
        not soft,
        mcp,
        name,
        id,
    )

    if row is None:
        raise ValueError("Failed to create agent_drafts entry")

    draft_id = row["id"]
    created_at = row["created_at"]
    actual_active = row["active"]

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
        ("agent_drafts_qualities_connection", "qualities_id", quality_ids or []),
        ("agent_drafts_rubrics_connection", "rubrics_id", rubric_ids or []),
        ("agent_drafts_prompts_connection", "prompts_id", prompt_ids or []),
        ("agent_drafts_instructions_connection", "instructions_id", instruction_ids or []),
        ("agent_drafts_agents_connection", "agents_id", agent_ids or []),
    ]

    _pending = pending_ids or set()
    for table, col, ids in connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (draft_id, {col}, active) VALUES ($1, $2, $3) "
                f"ON CONFLICT (draft_id, {col}) DO UPDATE SET active = EXCLUDED.active",
                draft_id,
                rid,
                False if soft else (rid not in _pending),
            )

    def _committed(ids: list[UUID] | None) -> list[str]:
        return [str(rid) for rid in (ids or [])]

    def _pending_only(ids: list[UUID] | None) -> list[str]:
        if soft:
            return [str(rid) for rid in (ids or [])]
        return [str(rid) for rid in (ids or []) if rid in _pending]

    fresh_row = {
        "id": str(draft_id),
        "created_at": created_at.isoformat(),
        "generated": True,
        "mcp": mcp,
        "active": actual_active,
        "session_id": str(session_id),
        "name": name,
        "name_ids": _committed(name_ids),
        "description_ids": _committed(description_ids),
        "flag_ids": _committed(flag_ids),
        "department_ids": _committed(department_ids),
        "model_ids": _committed(model_ids),
        "tool_ids": _committed(tool_ids),
        "profile_ids": _committed(profile_ids),
        "reasoning_level_ids": _committed(reasoning_level_ids),
        "temperature_level_ids": _committed(temperature_level_ids),
        "voice_ids": _committed(voice_ids),
        "quality_ids": _committed(quality_ids),
        "rubric_ids": _committed(rubric_ids),
        "prompt_ids": _committed(prompt_ids),
        "instruction_ids": _committed(instruction_ids),
        "agent_ids": _committed(agent_ids),
        "pending_name_ids": _pending_only(name_ids),
        "pending_description_ids": _pending_only(description_ids),
        "pending_flag_ids": _pending_only(flag_ids),
        "pending_department_ids": _pending_only(department_ids),
        "pending_model_ids": _pending_only(model_ids),
        "pending_tool_ids": _pending_only(tool_ids),
        "pending_reasoning_level_ids": _pending_only(reasoning_level_ids),
        "pending_temperature_level_ids": _pending_only(temperature_level_ids),
        "pending_voice_ids": _pending_only(voice_ids),
        "pending_quality_ids": _pending_only(quality_ids),
        "pending_rubric_ids": _pending_only(rubric_ids),
        "pending_prompt_ids": _pending_only(prompt_ids),
        "pending_instruction_ids": _pending_only(instruction_ids),
        "pending_agent_ids": _pending_only(agent_ids),
    }
    await write_back_row(
        redis,
        "agent_drafts",
        draft_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateAgentDraftResponse(id=draft_id)
