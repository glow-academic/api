"""Invocation drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.invocation_drafts.types import (
    CreateInvocationDraftResponse,
)


async def create_invocation_draft(
    conn: asyncpg.Connection,
    session_id: UUID,
    *,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    name: str = "",
    department_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    endpoint_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    key_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    pricing_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    reasoning_level_ids: list[UUID] | None = None,
    temperature_level_ids: list[UUID] | None = None,
    value_id: UUID | None = None,
    voice_ids: list[UUID] | None = None,
    modality_ids: list[UUID] | None = None,
    quality_ids: list[UUID] | None = None,
    model_flag_ids: list[UUID] | None = None,
    model_position_ids: list[UUID] | None = None,
    model_rubric_ids: list[UUID] | None = None,
    pending_ids: set[UUID] | None = None,
) -> CreateInvocationDraftResponse:
    """Create an invocation_drafts entry with optional connection table links."""
    draft_id = await conn.fetchval(
        """
        INSERT INTO invocation_drafts_entry (id, session_id, active, mcp, generated, name)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, true, $4)
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id
        """,
        session_id,
        not soft,
        mcp,
        name,
        id,
    )

    if draft_id is None:
        raise ValueError("Failed to create invocation_drafts entry")

    # Connections using `draft_id` as FK column
    draft_fk_connections: list[tuple[str, str, list[UUID]]] = [
        (
            "invocation_drafts_departments_connection",
            "departments_id",
            department_ids or [],
        ),
        (
            "invocation_drafts_descriptions_connection",
            "descriptions_id",
            description_ids or [],
        ),
        ("invocation_drafts_flags_connection", "flags_id", flag_ids or []),
        ("invocation_drafts_keys_connection", "keys_id", key_ids or []),
        ("invocation_drafts_names_connection", "names_id", name_ids or []),
        ("invocation_drafts_profiles_connection", "profiles_id", profile_ids or []),
        (
            "invocation_drafts_reasoning_levels_connection",
            "reasoning_levels_id",
            reasoning_level_ids or [],
        ),
        (
            "invocation_drafts_temperature_levels_connection",
            "temperature_levels_id",
            temperature_level_ids or [],
        ),
        ("invocation_drafts_voices_connection", "voices_id", voice_ids or []),
        ("invocation_drafts_modalities_connection", "modalities_id", modality_ids or []),
        ("invocation_drafts_qualities_connection", "qualities_id", quality_ids or []),
        ("invocation_drafts_model_flags_connection", "model_flags_id", model_flag_ids or []),
        ("invocation_drafts_model_positions_connection", "model_positions_id", model_position_ids or []),
        ("invocation_drafts_model_rubrics_connection", "model_rubrics_id", model_rubric_ids or []),
    ]

    pending = pending_ids or set()
    for table, col, ids in draft_fk_connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (draft_id, {col}, active) VALUES ($1, $2, $3) "
                f"ON CONFLICT (draft_id, {col}) DO UPDATE SET active = EXCLUDED.active",
                draft_id,
                rid,
                False if soft else (rid not in pending),
            )

    # Connections using `invocation_drafts_id` as FK column
    invocation_fk_connections: list[tuple[str, str, list[UUID]]] = [
        (
            "invocation_drafts_endpoints_connection",
            "endpoints_id",
            endpoint_ids or [],
        ),
        (
            "invocation_drafts_pricing_connection",
            "pricing_id",
            pricing_ids or [],
        ),
        (
            "invocation_drafts_values_connection",
            "values_id",
            [value_id] if value_id else [],
        ),
    ]

    for table, col, ids in invocation_fk_connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (invocation_drafts_id, {col}, active) VALUES ($1, $2, $3) "
                f"ON CONFLICT (invocation_drafts_id, {col}) DO UPDATE SET active = EXCLUDED.active",
                draft_id,
                rid,
                False if soft else (rid not in pending),
            )

    return CreateInvocationDraftResponse(id=draft_id)
