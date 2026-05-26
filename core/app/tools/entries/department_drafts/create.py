"""Department drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.department_drafts.types import (
    CreateDepartmentDraftResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_department_draft(
    conn: asyncpg.Connection,
    redis: Redis,
    session_id: UUID,
    *,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    name: str = "",
    description_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    setting_ids: list[UUID] | None = None,
    pending_ids: set[UUID] | None = None,
) -> CreateDepartmentDraftResponse:
    """Create a department_drafts entry with optional connection table links.

    pending_ids: resource IDs that should be created with active=false.
    soft: when True, all connections are written as inactive.
    """
    row = await conn.fetchrow(
        """
        INSERT INTO department_drafts_entry (id, session_id, active, mcp, generated, name)
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
        raise ValueError("Failed to create department_drafts entry")

    draft_id = row["id"]
    created_at = row["created_at"]
    actual_active = row["active"]

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

    def _active_only(ids: list[UUID] | None) -> list[str]:
        # Connections written with active=true (committed, not pending, not soft)
        if soft:
            return []
        return [str(rid) for rid in (ids or []) if rid not in _pending]

    def _inactive_only(ids: list[UUID] | None) -> list[str]:
        # Connections written with active=false (pending, or all when soft)
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
        "description_ids": _active_only(description_ids),
        "flag_ids": _active_only(flag_ids),
        "name_ids": _active_only(name_ids),
        "profile_ids": [str(rid) for rid in (profile_ids or [])],  # No active filter on profile in GET
        "setting_ids": _active_only(setting_ids),
        "pending_description_ids": _inactive_only(description_ids),
        "pending_flag_ids": _inactive_only(flag_ids),
        "pending_name_ids": _inactive_only(name_ids),
        "pending_setting_ids": _inactive_only(setting_ids),
    }
    await write_back_row(
        redis,
        "department_drafts",
        draft_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateDepartmentDraftResponse(id=draft_id)
