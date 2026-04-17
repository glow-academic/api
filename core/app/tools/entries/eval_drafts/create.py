"""Eval drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.eval_drafts.types import CreateEvalDraftResponse


async def create_eval_draft(
    conn: asyncpg.Connection,
    session_id: UUID,
    *,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    department_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    model_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    rubric_ids: list[UUID] | None = None,
    pending_ids: set[UUID] | None = None,
) -> CreateEvalDraftResponse:
    """Create an eval_drafts entry with optional connection table links.

    pending_ids: resource IDs that should be written with active=false.
    soft: when True, all connections are written inactive.
    """
    draft_id = await conn.fetchval(
        """
        INSERT INTO eval_drafts_entry (id, session_id, active, mcp, generated)
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
        raise ValueError("Failed to create eval_drafts entry")

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

    return CreateEvalDraftResponse(id=draft_id)
