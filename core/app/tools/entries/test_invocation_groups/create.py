"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.test_invocation_groups.types import (
    CreateTestInvocationGroupsResponse,
)


async def create_test_invocation_groups(
    conn: asyncpg.Connection,
    test_invocation_id: UUID,
    *,
    id: UUID | None = None,
    agent_ids: list[UUID] | None = None,
    group_ids: list[UUID] | None = None,
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
) -> CreateTestInvocationGroupsResponse:
    """Create a test_invocation_groups entry with optional connections."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO test_invocation_groups_entry (id, test_invocation_id, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, true)
        RETURNING id
        """,
        test_invocation_id,
        not soft,
        mcp,
        id,
    )

    if group_ids:
        for group_id in group_ids:
            await conn.execute(
                """
                INSERT INTO test_invocation_groups_groups_connection
                    (test_invocation_groups_id, groups_id)
                VALUES ($1, $2)
                """,
                entry_id,
                group_id,
            )

    connections = [
        ("test_invocation_groups_agents_connection", "agents_id", agent_ids or []),
        (
            "test_invocation_groups_reasoning_levels_connection",
            "reasoning_levels_id",
            reasoning_level_ids or [],
        ),
        (
            "test_invocation_groups_temperature_levels_connection",
            "temperature_levels_id",
            temperature_level_ids or [],
        ),
        ("test_invocation_groups_voices_connection", "voices_id", voice_ids or []),
        ("test_invocation_groups_prompts_connection", "prompts_id", prompt_ids or []),
        (
            "test_invocation_groups_instructions_connection",
            "instructions_id",
            instruction_ids or [],
        ),
        ("test_invocation_groups_tools_connection", "tools_id", tool_ids or []),
        (
            "test_invocation_groups_qualities_connection",
            "qualities_id",
            quality_ids or [],
        ),
        (
            "test_invocation_groups_modalities_connection",
            "modalities_id",
            modality_ids or [],
        ),
    ]
    for table, col, ids in connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (test_invocation_groups_id, {col}) VALUES ($1, $2)",
                entry_id,
                rid,
            )

    return CreateTestInvocationGroupsResponse(id=entry_id)
