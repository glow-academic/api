"""Profile drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.profile_drafts.types import CreateProfileDraftResponse


async def create_profile_draft(
    conn: asyncpg.Connection,
    group_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    version: int = 0,
    mcp: bool = False,
    soft: bool = False,
    profile_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    email_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    request_limit_ids: list[UUID] | None = None,
    role_ids: list[UUID] | None = None,
) -> CreateProfileDraftResponse:
    """Create a profile_drafts entry with optional connection table links."""
    draft_id = await conn.fetchval(
        """
        INSERT INTO profile_drafts_entry (id, group_id, session_id, version, active, mcp, generated)
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
        (
            "profile_drafts_request_limits_connection",
            "request_limits_id",
            request_limit_ids or [],
        ),
        ("profile_drafts_roles_connection", "roles_id", role_ids or []),
    ]

    for table, col, ids in connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (draft_id, {col}) VALUES ($1, $2)",
                draft_id,
                rid,
            )

    return CreateProfileDraftResponse(id=draft_id)
