"""Rubric drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.rubric_drafts.types import CreateRubricDraftResponse


async def create_rubric_draft(
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
    name_ids: list[UUID] | None = None,
    point_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    standard_group_ids: list[UUID] | None = None,
    standard_ids: list[UUID] | None = None,
) -> CreateRubricDraftResponse:
    """Create a rubric_drafts entry with optional connection table links."""
    draft_id = await conn.fetchval(
        """
        INSERT INTO rubric_drafts_entry (id, group_id, session_id, version, active, mcp, generated)
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
        raise ValueError("Failed to create rubric_drafts entry")

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
                f"INSERT INTO {table} (draft_id, {col}) VALUES ($1, $2)",
                draft_id,
                rid,
            )

    return CreateRubricDraftResponse(id=draft_id)
