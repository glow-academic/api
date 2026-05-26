"""Parameter drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.parameter_drafts.types import (
    CreateParameterDraftResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_parameter_draft(
    conn: asyncpg.Connection,
    redis: Redis,
    session_id: UUID,
    *,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    name: str = "",
    department_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    field_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    pending_ids: set[UUID] | None = None,
) -> CreateParameterDraftResponse:
    """Create a parameter_drafts entry with optional connection table links.

    pending_ids: resource IDs that should be created with active=false (pending acceptance).
    soft: when True, ALL connections are active=false (overrides pending_ids).
    """
    row = await conn.fetchrow(
        """
        INSERT INTO parameter_drafts_entry (id, session_id, active, mcp, generated, name)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, true, $4)
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id, created_at, active
        """,
        session_id,
        not soft,
        mcp,
        name,
        id,
    )

    if row is None:
        raise ValueError("Failed to create parameter_drafts entry")

    draft_id = row["id"]
    created_at = row["created_at"]
    actual_active = row["active"]

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

    def _all(ids: list[UUID] | None) -> list[str]:
        return [str(rid) for rid in (ids or [])]

    def _pending_only(ids: list[UUID] | None) -> list[str]:
        if soft:
            return [str(rid) for rid in (ids or [])]
        return [str(rid) for rid in (ids or []) if rid in _pending]

    fresh_row = {
        "id": str(draft_id),
        "created_at": created_at.isoformat(),
        "generated": True,
        "mcp": mcp,
        "active": actual_active,
        "session_id": str(session_id),
        "name": name,
        "department_ids": _all(department_ids),
        "description_ids": _all(description_ids),
        "field_ids": _all(field_ids),
        "flag_ids": _all(flag_ids),
        "name_ids": _all(name_ids),
        "profile_ids": _all(profile_ids),
        "pending_department_ids": _pending_only(department_ids),
        "pending_description_ids": _pending_only(description_ids),
        "pending_field_ids": _pending_only(field_ids),
        "pending_flag_ids": _pending_only(flag_ids),
        "pending_name_ids": _pending_only(name_ids),
    }
    await write_back_row(
        redis,
        "parameter_drafts",
        draft_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateParameterDraftResponse(id=draft_id)
