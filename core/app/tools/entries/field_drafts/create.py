"""Field drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.field_drafts.types import CreateFieldDraftResponse


async def create_field_draft(
    conn: asyncpg.Connection,
    session_id: UUID,
    *,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    name: str = "",
    conditional_parameter_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    pending_ids: set[UUID] | None = None,
) -> CreateFieldDraftResponse:
    """Create a field_drafts entry with optional connection table links.

    pending_ids: resource IDs that should be created with active=false (pending acceptance).
    soft: when True, ALL connections are active=false (overrides pending_ids).
    """
    draft_id = await conn.fetchval(
        """
        INSERT INTO field_drafts_entry (id, session_id, active, mcp, generated, name)
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
        raise ValueError("Failed to create field_drafts entry")

    connections: list[tuple[str, str, list[UUID]]] = [
        (
            "field_drafts_conditional_parameters_connection",
            "conditional_parameters_id",
            conditional_parameter_ids or [],
        ),
        ("field_drafts_departments_connection", "departments_id", department_ids or []),
        (
            "field_drafts_descriptions_connection",
            "descriptions_id",
            description_ids or [],
        ),
        ("field_drafts_flags_connection", "flags_id", flag_ids or []),
        ("field_drafts_names_connection", "names_id", name_ids or []),
        ("field_drafts_profiles_connection", "profiles_id", profile_ids or []),
    ]

    _pending = pending_ids or set()
    for table, col, ids in connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (draft_id, {col}, active) VALUES ($1, $2, $3) "
                f"ON CONFLICT (draft_id, {col}) DO UPDATE SET active = EXCLUDED.active",
                draft_id,
                rid,
                False if soft else (rid not in _pending),
            )

    return CreateFieldDraftResponse(id=draft_id)
