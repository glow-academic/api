"""Profile drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.profile_drafts.types import CreateProfileDraftResponse
from app.utils.cache.hedged_row import write_back_row


async def create_profile_draft(
    conn: asyncpg.Connection,
    redis: Redis,
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
    row = await conn.fetchrow(
        """
        INSERT INTO profile_drafts_entry (id, session_id, active, mcp, generated, name)
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
        raise ValueError("Failed to create profile_drafts entry")

    draft_id = row["id"]
    created_at = row["created_at"]
    actual_active = row["active"]

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
        "profile_ids": _all(profile_ids),
        "department_ids": _all(department_ids),
        "email_ids": _all(email_ids),
        "flag_ids": _all(flag_ids),
        "name_ids": _all(name_ids),
        "role_ids": _all(role_ids),
        "primary_department_ids": _all(primary_department_ids),
        "pending_department_ids": _pending_only(department_ids),
        "pending_email_ids": _pending_only(email_ids),
        "pending_flag_ids": _pending_only(flag_ids),
        "pending_name_ids": _pending_only(name_ids),
        "pending_role_ids": _pending_only(role_ids),
        "pending_primary_department_ids": _pending_only(primary_department_ids),
    }
    await write_back_row(
        redis,
        "profile_drafts",
        draft_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateProfileDraftResponse(id=draft_id)
