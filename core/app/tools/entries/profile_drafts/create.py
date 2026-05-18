"""Profile drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.profile_drafts.types import CreateProfileDraftResponse


async def create_profile_draft(
    conn: asyncpg.Connection,
    session_id: UUID,
    *,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    name: str = "",
    profile_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    email_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    role_ids: list[UUID] | None = None,
    primary_department_ids: list[UUID] | None = None,
    pending_ids: set[UUID] | None = None,
) -> CreateProfileDraftResponse:
    """Create a profile_drafts entry with optional connection table links.

    pending_ids: resource IDs that should be created with active=false.
    soft: when True, all entry + connection rows are active=false.
    """
    draft_id = await conn.fetchval(
        """
        INSERT INTO profile_drafts_entry (id, session_id, active, mcp, generated, name)
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
        raise ValueError("Failed to create profile_drafts entry")

    connections: list[tuple[str, str, list[UUID]]] = [
        ("profile_drafts_profiles_connection", "profiles_id", profile_ids or []),
        (
            "profile_drafts_departments_connection",
            "departments_id",
            department_ids or [],
        ),
        ("profile_drafts_emails_connection", "emails_id", email_ids or []),
        ("profile_drafts_flags_connection", "flags_id", flag_ids or []),
        ("profile_drafts_names_connection", "names_id", name_ids or []),
        ("profile_drafts_roles_connection", "roles_id", role_ids or []),
        (
            "profile_drafts_primary_departments_connection",
            "primary_departments_id",
            primary_department_ids or [],
        ),
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

    return CreateProfileDraftResponse(id=draft_id)
