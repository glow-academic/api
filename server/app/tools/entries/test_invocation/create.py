"""Test invocation CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.test_invocation.types import (
    CreateTestInvocationResponse,
)


async def create_test_invocation(
    conn: asyncpg.Connection,
    *,
    id: UUID | None = None,
    test_id: UUID | None = None,
    call_id: UUID | None = None,
    title: str = "",
    group_id: UUID | None = None,
    use_custom: bool = False,
    position: int = 0,
    config_signature: str | None = None,
    mcp: bool = False,
    soft: bool = False,
    agent_ids: list[UUID] | None = None,
    rubric_ids: list[UUID] | None = None,
    quality_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    voice_ids: list[UUID] | None = None,
    reasoning_level_ids: list[UUID] | None = None,
    temperature_level_ids: list[UUID] | None = None,
    modality_ids: list[UUID] | None = None,
) -> CreateTestInvocationResponse:
    """Create a test_invocation_entry row."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO test_invocation_entry (
            id, test_id, call_id, title, group_id,
            use_custom, "position", config_signature, active, mcp, generated
        )
        VALUES (COALESCE($10, uuidv7()), $1, $2, $3, $4, $5, $6, $7, $8, $9, true)
        RETURNING id
        """,
        test_id,
        call_id,
        title,
        group_id,
        use_custom,
        position,
        config_signature,
        not soft,
        mcp,
        id,
    )

    if entry_id is None:
        raise ValueError("Failed to create test_invocation entry")

    connections = [
        ("test_invocation_agents_connection", "agents_id", agent_ids or []),
        ("test_invocation_rubrics_connection", "rubrics_id", rubric_ids or []),
        ("test_invocation_qualities_connection", "qualities_id", quality_ids or []),
        (
            "test_invocation_departments_connection",
            "departments_id",
            department_ids or [],
        ),
        ("test_invocation_voices_connection", "voices_id", voice_ids or []),
        (
            "test_invocation_reasoning_levels_connection",
            "reasoning_levels_id",
            reasoning_level_ids or [],
        ),
        (
            "test_invocation_temperature_levels_connection",
            "temperature_levels_id",
            temperature_level_ids or [],
        ),
        (
            "test_invocation_modalities_connection",
            "modalities_id",
            modality_ids or [],
        ),
    ]
    for table, col, ids in connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (test_invocation_id, {col}) VALUES ($1, $2)",
                entry_id,
                rid,
            )

    return CreateTestInvocationResponse(id=entry_id)
