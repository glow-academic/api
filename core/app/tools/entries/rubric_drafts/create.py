"""Rubric drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.rubric_drafts.types import CreateRubricDraftResponse
from app.utils.cache.hedged_row import write_back_row


async def create_rubric_draft(
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
    flag_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    point_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    standard_group_ids: list[UUID] | None = None,
    standard_ids: list[UUID] | None = None,
    pending_ids: set[UUID] | None = None,
) -> CreateRubricDraftResponse:
    """Create a rubric_drafts entry with optional connection table links."""
    row = await conn.fetchrow(
        """
        INSERT INTO rubric_drafts_entry (id, session_id, active, mcp, generated, name)
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
        raise ValueError("Failed to create rubric_drafts entry")

    draft_id = row["id"]
    created_at = row["created_at"]
    actual_active = row["active"]

    _pending = pending_ids or set()

    connections: list[tuple[str, str, list[UUID]]] = [
        (
            "rubric_drafts_departments_connection",
            "departments_id",
            department_ids or [],
        ),
        (
            "rubric_drafts_descriptions_connection",
            "descriptions_id",
            description_ids or [],
        ),
        ("rubric_drafts_flags_connection", "flags_id", flag_ids or []),
        ("rubric_drafts_names_connection", "names_id", name_ids or []),
        ("rubric_drafts_points_connection", "points_id", point_ids or []),
        ("rubric_drafts_profiles_connection", "profiles_id", profile_ids or []),
        (
            "rubric_drafts_standard_groups_connection",
            "standard_groups_id",
            standard_group_ids or [],
        ),
        ("rubric_drafts_standards_connection", "standards_id", standard_ids or []),
    ]

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
        if soft:
            return []
        return [str(rid) for rid in (ids or []) if rid not in _pending]

    def _inactive_only(ids: list[UUID] | None) -> list[str]:
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
        "department_ids": _active_only(department_ids),
        "description_ids": _active_only(description_ids),
        "flag_ids": _active_only(flag_ids),
        "name_ids": _active_only(name_ids),
        "point_ids": _active_only(point_ids),
        "profile_ids": [str(rid) for rid in (profile_ids or [])],
        "standard_group_ids": _active_only(standard_group_ids),
        "standard_ids": _active_only(standard_ids),
        "pending_department_ids": _inactive_only(department_ids),
        "pending_description_ids": _inactive_only(description_ids),
        "pending_flag_ids": _inactive_only(flag_ids),
        "pending_name_ids": _inactive_only(name_ids),
        "pending_point_ids": _inactive_only(point_ids),
        "pending_standard_group_ids": _inactive_only(standard_group_ids),
        "pending_standard_ids": _inactive_only(standard_ids),
    }
    await write_back_row(
        redis,
        "rubric_drafts",
        draft_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateRubricDraftResponse(id=draft_id)
