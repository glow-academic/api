"""Auth drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.auth_drafts.types import CreateAuthDraftResponse


async def create_auth_draft(
    conn: asyncpg.Connection,
    group_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    version: int = 0,
    mcp: bool = False,
    soft: bool = False,
    department_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    item_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    protocol_ids: list[UUID] | None = None,
    slug_ids: list[UUID] | None = None,
) -> CreateAuthDraftResponse:
    """Create an auth_drafts entry with optional connection table links."""
    draft_id = await conn.fetchval(
        """
        INSERT INTO auth_drafts_entry (id, group_id, session_id, version, active, mcp, generated)
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
        raise ValueError("Failed to create auth_drafts entry")

    connections: list[tuple[str, str, list[UUID]]] = [
        ("auth_drafts_departments_connection", "departments_id", department_ids or []),
        (
            "auth_drafts_descriptions_connection",
            "descriptions_id",
            description_ids or [],
        ),
        ("auth_drafts_flags_connection", "flags_id", flag_ids or []),
        ("auth_drafts_items_connection", "items_id", item_ids or []),
        ("auth_drafts_names_connection", "names_id", name_ids or []),
        ("auth_drafts_profiles_connection", "profiles_id", profile_ids or []),
        ("auth_drafts_protocols_connection", "protocols_id", protocol_ids or []),
        ("auth_drafts_slugs_connection", "slugs_id", slug_ids or []),
    ]

    for table, col, ids in connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (draft_id, {col}) VALUES ($1, $2)",
                draft_id,
                rid,
            )

    return CreateAuthDraftResponse(id=draft_id)
