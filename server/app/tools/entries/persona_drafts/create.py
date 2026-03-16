"""Persona drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.persona_drafts.types import CreatePersonaDraftResponse


async def create_persona_draft(
    conn: asyncpg.Connection,
    group_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    version: int = 0,
    mcp: bool = False,
    soft: bool = False,
    color_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    example_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    icon_ids: list[UUID] | None = None,
    instruction_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    parameter_field_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    voice_ids: list[UUID] | None = None,
) -> CreatePersonaDraftResponse:
    """Create a persona_drafts entry with optional connection table links."""
    draft_id = await conn.fetchval(
        """
        INSERT INTO persona_drafts_entry (id, group_id, session_id, version, active, mcp, generated)
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
        raise ValueError("Failed to create persona_drafts entry")

    connections: list[tuple[str, str, list[UUID]]] = [
        ("persona_drafts_colors_connection", "colors_id", color_ids or []),
        (
            "persona_drafts_departments_connection",
            "departments_id",
            department_ids or [],
        ),
        (
            "persona_drafts_descriptions_connection",
            "descriptions_id",
            description_ids or [],
        ),
        ("persona_drafts_examples_connection", "examples_id", example_ids or []),
        ("persona_drafts_flags_connection", "flags_id", flag_ids or []),
        ("persona_drafts_icons_connection", "icons_id", icon_ids or []),
        (
            "persona_drafts_instructions_connection",
            "instructions_id",
            instruction_ids or [],
        ),
        ("persona_drafts_names_connection", "names_id", name_ids or []),
        (
            "persona_drafts_parameter_fields_connection",
            "parameter_fields_id",
            parameter_field_ids or [],
        ),
        ("persona_drafts_profiles_connection", "profiles_id", profile_ids or []),
        ("persona_drafts_voices_connection", "voices_id", voice_ids or []),
    ]

    for table, col, ids in connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (draft_id, {col}) VALUES ($1, $2)",
                draft_id,
                rid,
            )

    return CreatePersonaDraftResponse(id=draft_id)
