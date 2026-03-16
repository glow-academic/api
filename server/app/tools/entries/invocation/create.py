"""Invocation CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.invocation.types import CreateInvocationResponse
from app.tools.entries.sessions.create import create_session


async def create_invocation(
    conn: asyncpg.Connection,
    benchmark_id: UUID,
    id: UUID | None = None,
    session_id: UUID | None = None,
    use_custom: bool = False,
    position: int = 0,
    mcp: bool = False,
    soft: bool = False,
    department_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    key_ids: list[UUID] | None = None,
    modality_ids: list[UUID] | None = None,
    model_flag_ids: list[UUID] | None = None,
    model_position_ids: list[UUID] | None = None,
    model_rubric_ids: list[UUID] | None = None,
    model_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    quality_ids: list[UUID] | None = None,
    reasoning_level_ids: list[UUID] | None = None,
    temperature_level_ids: list[UUID] | None = None,
    voice_ids: list[UUID] | None = None,
) -> CreateInvocationResponse:
    """Create an invocation entry with optional connection table links."""
    if session_id is None:
        session = await create_session(conn, mcp=mcp, soft=soft)
        session_id = session.id

    invocation_id = await conn.fetchval(
        """
        INSERT INTO invocation_entry (id, benchmark_id, session_id, use_custom, "position", active, mcp, generated)
        VALUES (COALESCE($7, uuidv7()), $1, $2, $3, $4, $5, $6, true)
        RETURNING id
        """,
        benchmark_id,
        session_id,
        use_custom,
        position,
        not soft,
        mcp,
        id,
    )

    if invocation_id is None:
        raise ValueError("Failed to create invocation entry")

    connections: list[tuple[str, str, list[UUID]]] = [
        ("invocation_departments_connection", "departments_id", department_ids or []),
        (
            "invocation_descriptions_connection",
            "descriptions_id",
            description_ids or [],
        ),
        ("invocation_flags_connection", "flags_id", flag_ids or []),
        ("invocation_keys_connection", "keys_id", key_ids or []),
        ("invocation_modalities_connection", "modalities_id", modality_ids or []),
        ("invocation_model_flags_connection", "model_flags_id", model_flag_ids or []),
        (
            "invocation_model_positions_connection",
            "model_positions_id",
            model_position_ids or [],
        ),
        (
            "invocation_model_rubrics_connection",
            "model_rubrics_id",
            model_rubric_ids or [],
        ),
        ("invocation_models_connection", "models_id", model_ids or []),
        ("invocation_names_connection", "names_id", name_ids or []),
        ("invocation_qualities_connection", "qualities_id", quality_ids or []),
        (
            "invocation_reasoning_levels_connection",
            "reasoning_levels_id",
            reasoning_level_ids or [],
        ),
        (
            "invocation_temperature_levels_connection",
            "temperature_levels_id",
            temperature_level_ids or [],
        ),
        ("invocation_voices_connection", "voices_id", voice_ids or []),
    ]

    for table, col, ids in connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (invocation_id, {col}) VALUES ($1, $2)",
                invocation_id,
                rid,
            )

    return CreateInvocationResponse(id=invocation_id)
