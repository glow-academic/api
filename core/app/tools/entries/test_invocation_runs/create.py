"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.test_invocation_runs.types import (
    CreateTestInvocationRunsResponse,
)


async def create_test_invocation_runs(
    conn: asyncpg.Connection,
    test_invocation_id: UUID,
    *,
    id: UUID | None = None,
    agent_ids: list[UUID] | None = None,
    reasoning_level_ids: list[UUID] | None = None,
    temperature_level_ids: list[UUID] | None = None,
    voice_ids: list[UUID] | None = None,
    prompt_ids: list[UUID] | None = None,
    instruction_ids: list[UUID] | None = None,
    tool_ids: list[UUID] | None = None,
    quality_ids: list[UUID] | None = None,
    modality_ids: list[UUID] | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateTestInvocationRunsResponse:
    """Create a test_invocation_runs entry with optional connections."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO test_invocation_runs_entry (id, test_invocation_id, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, true)
        RETURNING id
        """,
        test_invocation_id,
        not soft,
        mcp,
        id,
    )

    connections = [
        ("test_invocation_runs_agents_connection", "agents_id", agent_ids or []),
        (
            "test_invocation_runs_reasoning_levels_connection",
            "reasoning_levels_id",
            reasoning_level_ids or [],
        ),
        (
            "test_invocation_runs_temperature_levels_connection",
            "temperature_levels_id",
            temperature_level_ids or [],
        ),
        ("test_invocation_runs_voices_connection", "voices_id", voice_ids or []),
        ("test_invocation_runs_prompts_connection", "prompts_id", prompt_ids or []),
        (
            "test_invocation_runs_instructions_connection",
            "instructions_id",
            instruction_ids or [],
        ),
        ("test_invocation_runs_tools_connection", "tools_id", tool_ids or []),
        (
            "test_invocation_runs_qualities_connection",
            "qualities_id",
            quality_ids or [],
        ),
        (
            "test_invocation_runs_modalities_connection",
            "modalities_id",
            modality_ids or [],
        ),
    ]
    for table, col, ids in connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (test_invocation_runs_id, {col}) VALUES ($1, $2)",
                entry_id,
                rid,
            )

    return CreateTestInvocationRunsResponse(id=entry_id)
