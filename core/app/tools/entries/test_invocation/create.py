"""Test invocation CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.test_invocation.types import (
    CreateTestInvocationResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_test_invocation(
    conn: asyncpg.Connection,
    redis: Redis,
    *,
    id: UUID | None = None,
    test_id: UUID | None = None,
    call_id: UUID | None = None,
    title: str = "",
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
    row = await conn.fetchrow(
        """
        INSERT INTO test_invocation_entry (
            id, test_id, call_id, title,
            use_custom, "position", config_signature, active, mcp, generated
        )
        VALUES (COALESCE($9, uuidv7()), $1, $2, $3, $4, $5, $6, $7, $8, true)
        RETURNING id, created_at
        """,
        test_id,
        call_id,
        title,
        use_custom,
        position,
        config_signature,
        not soft,
        mcp,
        id,
    )

    if row is None:
        raise ValueError("Failed to create test_invocation entry")

    entry_id = row["id"]
    created_at = row["created_at"]

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

    # Write-back cache row matching test_invocation_mv GET response shape.
    # Junction-derived bundle fields (rubric_id, quality_id, voice_id, etc.)
    # are derived from the connection inserts above; grade/completion fields
    # are aggregates the MV computes from sibling entries, default to None
    # at create-time.
    fresh_row = {
        "invocation_id": str(entry_id),
        "test_id": str(test_id) if test_id else None,
        "group_id": None,
        "invocation_created_at": created_at.isoformat(),
        "invocation_title": title,
        "use_custom": use_custom,
        "position": position,
        "invocation_completed": False,
        "grade_id": None,
        "grade_score": None,
        "grade_passed": None,
        "grade_time_taken": None,
        "rubric_id": str(rubric_ids[0]) if rubric_ids else None,
        "agent_ids": [str(a) for a in (agent_ids or [])],
        "quality_id": str(quality_ids[0]) if quality_ids else None,
        "department_ids": [str(d) for d in (department_ids or [])],
        "voice_id": str(voice_ids[0]) if voice_ids else None,
        "temperature_level_id": (
            str(temperature_level_ids[0]) if temperature_level_ids else None
        ),
        "reasoning_level_id": (
            str(reasoning_level_ids[0]) if reasoning_level_ids else None
        ),
        "modality_ids": [str(m) for m in (modality_ids or [])],
    }
    await write_back_row(
        redis,
        "test_invocation",
        entry_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateTestInvocationResponse(id=entry_id)
