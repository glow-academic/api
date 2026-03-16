"""Parameter drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.parameter_drafts.types import (
    CreateParameterDraftResponse,
)


async def create_parameter_draft(
    conn: asyncpg.Connection,
    group_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    version: int = 0,
    mcp: bool = False,
    soft: bool = False,
    department_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    field_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
) -> CreateParameterDraftResponse:
    """Create a parameter_drafts entry with optional connection table links."""
    draft_id = await conn.fetchval(
        """
        INSERT INTO parameter_drafts_entry (id, group_id, session_id, version, active, mcp, generated)
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
        raise ValueError("Failed to create parameter_drafts entry")

    connections: list[tuple[str, str, list[UUID]]] = [
        (
            "parameter_drafts_departments_connection",
            "departments_id",
            department_ids or [],
        ),
        (
            "parameter_drafts_descriptions_connection",
            "descriptions_id",
            description_ids or [],
        ),
        ("parameter_drafts_fields_connection", "fields_id", field_ids or []),
        ("parameter_drafts_flags_connection", "flags_id", flag_ids or []),
        ("parameter_drafts_names_connection", "names_id", name_ids or []),
        ("parameter_drafts_profiles_connection", "profiles_id", profile_ids or []),
    ]

    for table, col, ids in connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (draft_id, {col}) VALUES ($1, $2)",
                draft_id,
                rid,
            )

    return CreateParameterDraftResponse(id=draft_id)
