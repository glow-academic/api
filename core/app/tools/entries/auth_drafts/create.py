"""Auth drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.auth_drafts.types import CreateAuthDraftResponse
from app.utils.cache.hedged_row import write_back_row


async def create_auth_draft(
    conn: asyncpg.Connection,
    redis: Redis,
    session_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    name: str = "",
    department_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    item_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    protocol_ids: list[UUID] | None = None,
    slug_ids: list[UUID] | None = None,
    pending_ids: set[UUID] | None = None,
) -> CreateAuthDraftResponse:
    """Create an auth_drafts entry with optional connection table links."""
    row = await conn.fetchrow(
        """
        INSERT INTO auth_drafts_entry (id, session_id, active, mcp, generated, name)
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
        raise ValueError("Failed to create auth_drafts entry")

    draft_id = row["id"]
    created_at = row["created_at"]
    actual_active = row["active"]

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

    _pending = pending_ids or set()
    for table, col, ids in connections:
        for rid in ids:
            is_active = False if soft else (rid not in _pending)
            await conn.execute(
                f"INSERT INTO {table} (draft_id, {col}, active) VALUES ($1, $2, $3) "
                f"ON CONFLICT (draft_id, {col}) DO UPDATE SET active = EXCLUDED.active",
                draft_id,
                rid,
                is_active,
            )

    def _committed(ids: list[UUID] | None) -> list[str]:
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
        "department_ids": _committed(department_ids),
        "description_ids": _committed(description_ids),
        "flag_ids": _committed(flag_ids),
        "item_ids": _committed(item_ids),
        "name_ids": _committed(name_ids),
        "profile_ids": _committed(profile_ids),
        "protocol_ids": _committed(protocol_ids),
        "slug_ids": _committed(slug_ids),
        "pending_department_ids": _pending_only(department_ids),
        "pending_description_ids": _pending_only(description_ids),
        "pending_flag_ids": _pending_only(flag_ids),
        "pending_item_ids": _pending_only(item_ids),
        "pending_name_ids": _pending_only(name_ids),
        "pending_protocol_ids": _pending_only(protocol_ids),
        "pending_slug_ids": _pending_only(slug_ids),
    }
    await write_back_row(
        redis,
        "auth_drafts",
        draft_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateAuthDraftResponse(id=draft_id)
