"""Provider drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.provider_drafts.types import (
    CreateProviderDraftResponse,
)


async def create_provider_draft(
    conn: asyncpg.Connection,
    session_id: UUID,
    *,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    department_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    endpoint_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    key_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    value_id: UUID | None = None,
    pending_ids: set[UUID] | None = None,
) -> CreateProviderDraftResponse:
    """Create a provider_drafts entry with optional connection table links.

    pending_ids: resource IDs that should be created with active=false.
    soft: when True, all entry + connection rows are active=false.
    """
    draft_id = await conn.fetchval(
        """
        INSERT INTO provider_drafts_entry (id, session_id, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, true)
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id
        """,
        session_id,
        not soft,
        mcp,
        id,
    )

    if draft_id is None:
        raise ValueError("Failed to create provider_drafts entry")

    connections: list[tuple[str, str, list[UUID]]] = [
        (
            "provider_drafts_departments_connection",
            "departments_id",
            department_ids or [],
        ),
        (
            "provider_drafts_descriptions_connection",
            "descriptions_id",
            description_ids or [],
        ),
        ("provider_drafts_endpoints_connection", "endpoints_id", endpoint_ids or []),
        ("provider_drafts_flags_connection", "flags_id", flag_ids or []),
        ("provider_drafts_keys_connection", "keys_id", key_ids or []),
        ("provider_drafts_names_connection", "names_id", name_ids or []),
        ("provider_drafts_profiles_connection", "profiles_id", profile_ids or []),
        ("provider_drafts_values_connection", "values_id", [value_id] if value_id else []),
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

    return CreateProviderDraftResponse(id=draft_id)
