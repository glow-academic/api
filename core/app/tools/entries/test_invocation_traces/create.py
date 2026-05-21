"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.test_invocation_traces.types import (
    CreateTestInvocationTracesResponse,
)


async def create_test_invocation_traces(
    conn: asyncpg.Connection,
    redis: Redis,
    test_invocation_id: UUID,
    *,
    id: UUID | None = None,
    run_id: UUID | None = None,
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
) -> CreateTestInvocationTracesResponse:
    """Create a test_invocation_traces entry with optional connections.

    `run_id` binds the trace to the historical run we're replaying against
    (manual flow) or to the live run we're recording (online eval flow).
    """
    entry_id = await conn.fetchval(
        """
        INSERT INTO test_invocation_traces_entry
            (id, test_invocation_id, run_id, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, true)
        RETURNING id
        """,
        test_invocation_id,
        run_id,
        not soft,
        mcp,
        id,
    )

    connections = [
        (
            "test_invocation_traces_reasoning_levels_connection",
            "reasoning_levels_id",
            reasoning_level_ids or [],
        ),
        (
            "test_invocation_traces_temperature_levels_connection",
            "temperature_levels_id",
            temperature_level_ids or [],
        ),
        ("test_invocation_traces_voices_connection", "voices_id", voice_ids or []),
        ("test_invocation_traces_prompts_connection", "prompts_id", prompt_ids or []),
        (
            "test_invocation_traces_instructions_connection",
            "instructions_id",
            instruction_ids or [],
        ),
        ("test_invocation_traces_tools_connection", "tools_id", tool_ids or []),
        (
            "test_invocation_traces_qualities_connection",
            "qualities_id",
            quality_ids or [],
        ),
        (
            "test_invocation_traces_modalities_connection",
            "modalities_id",
            modality_ids or [],
        ),
    ]
    for table, col, ids in connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (test_invocation_traces_id, {col}) VALUES ($1, $2)",
                entry_id,
                rid,
            )

    return CreateTestInvocationTracesResponse(id=entry_id)
