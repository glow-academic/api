"""Invocation drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.invocation_drafts.types import (
    CreateInvocationDraftResponse,
)


async def create_invocation_draft(
    conn: asyncpg.Connection,
    group_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    version: int = 0,
    mcp: bool = False,
    soft: bool = False,
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
    value_ids: list[UUID] | None = None,
    voice_ids: list[UUID] | None = None,
) -> CreateInvocationDraftResponse:
    """Create an invocation_drafts entry with optional connection table links."""
    draft_id = await conn.fetchval(
        """
        INSERT INTO invocation_drafts_entry (id, group_id, session_id, version, active, mcp, generated)
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
    ]

    for table, col, ids in draft_fk_connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (draft_id, {col}) VALUES ($1, $2)",
                draft_id,
                rid,
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
            value_ids or [],
        ),
    ]

    for table, col, ids in invocation_fk_connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (invocation_drafts_id, {col}) VALUES ($1, $2)",
                draft_id,
                rid,
            )

    return CreateInvocationDraftResponse(id=draft_id)
