"""Department drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.department_drafts.types import (
    CreateDepartmentDraftResponse,
)


async def create_department_draft(
    conn: asyncpg.Connection,
    group_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    version: int = 0,
    mcp: bool = False,
    soft: bool = False,
    description_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    setting_ids: list[UUID] | None = None,
) -> CreateDepartmentDraftResponse:
    """Create a department_drafts entry with optional connection table links."""
    draft_id = await conn.fetchval(
        """
        INSERT INTO department_drafts_entry (id, group_id, session_id, version, active, mcp, generated)
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
        raise ValueError("Failed to create department_drafts entry")

    connections: list[tuple[str, str, list[UUID]]] = [
        (
            "department_drafts_descriptions_connection",
            "descriptions_id",
            description_ids or [],
        ),
        ("department_drafts_flags_connection", "flags_id", flag_ids or []),
        ("department_drafts_names_connection", "names_id", name_ids or []),
        ("department_drafts_profiles_connection", "profiles_id", profile_ids or []),
        ("department_drafts_settings_connection", "settings_id", setting_ids or []),
    ]

    for table, col, ids in connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (draft_id, {col}) VALUES ($1, $2)",
                draft_id,
                rid,
            )

    return CreateDepartmentDraftResponse(id=draft_id)
