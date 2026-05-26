"""Eval drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.eval_drafts.types import CreateEvalDraftResponse
from app.utils.cache.hedged_row import write_back_row


async def create_eval_draft(
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
    model_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    rubric_ids: list[UUID] | None = None,
    model_flag_ids: list[UUID] | None = None,
    model_position_ids: list[UUID] | None = None,
    model_rubric_ids: list[UUID] | None = None,
    pending_ids: set[UUID] | None = None,
) -> CreateEvalDraftResponse:
    """Create an eval_drafts entry with optional connection table links.

    pending_ids: resource IDs that should be written with active=false.
    soft: when True, all connections are written inactive.
    """
    row = await conn.fetchrow(
        """
        INSERT INTO eval_drafts_entry (id, session_id, active, mcp, generated, name)
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
        raise ValueError("Failed to create eval_drafts entry")

    draft_id = row["id"]
    created_at = row["created_at"]
    actual_active = row["active"]

    connections: list[tuple[str, str, list[UUID]]] = [
        ("eval_drafts_departments_connection", "departments_id", department_ids or []),
        (
            "eval_drafts_descriptions_connection",
            "descriptions_id",
            description_ids or [],
        ),
        ("eval_drafts_flags_connection", "flags_id", flag_ids or []),
        ("eval_drafts_models_connection", "models_id", model_ids or []),
        ("eval_drafts_names_connection", "names_id", name_ids or []),
        ("eval_drafts_profiles_connection", "profiles_id", profile_ids or []),
        ("eval_drafts_rubrics_connection", "rubrics_id", rubric_ids or []),
        ("eval_drafts_model_flags_connection", "model_flags_id", model_flag_ids or []),
        ("eval_drafts_model_positions_connection", "model_positions_id", model_position_ids or []),
        ("eval_drafts_model_rubrics_connection", "model_rubrics_id", model_rubric_ids or []),
    ]

    pending = pending_ids or set()
    for table, col, ids in connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (draft_id, {col}, active) VALUES ($1, $2, $3) "
                f"ON CONFLICT (draft_id, {col}) DO UPDATE SET active = EXCLUDED.active",
                draft_id,
                rid,
                False if soft else (rid not in pending),
            )

    def _active_only(ids: list[UUID] | None) -> list[str]:
        if soft:
            return []
        return [str(rid) for rid in (ids or []) if rid not in pending]

    def _inactive_only(ids: list[UUID] | None) -> list[str]:
        if soft:
            return [str(rid) for rid in (ids or [])]
        return [str(rid) for rid in (ids or []) if rid in pending]

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
        "model_ids": _active_only(model_ids),
        "name_ids": _active_only(name_ids),
        "profile_ids": [str(rid) for rid in (profile_ids or [])],
        "rubric_ids": _active_only(rubric_ids),
        "model_flag_ids": _active_only(model_flag_ids),
        "model_position_ids": _active_only(model_position_ids),
        "model_rubric_ids": _active_only(model_rubric_ids),
        "pending_department_ids": _inactive_only(department_ids),
        "pending_description_ids": _inactive_only(description_ids),
        "pending_flag_ids": _inactive_only(flag_ids),
        "pending_model_ids": _inactive_only(model_ids),
        "pending_name_ids": _inactive_only(name_ids),
        "pending_rubric_ids": _inactive_only(rubric_ids),
        "pending_model_flag_ids": _inactive_only(model_flag_ids),
        "pending_model_position_ids": _inactive_only(model_position_ids),
        "pending_model_rubric_ids": _inactive_only(model_rubric_ids),
    }
    await write_back_row(
        redis,
        "eval_drafts",
        draft_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateEvalDraftResponse(id=draft_id)
