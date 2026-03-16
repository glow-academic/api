"""Tool drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.tool_drafts.types import CreateToolDraftResponse


async def create_tool_draft(
    conn: asyncpg.Connection,
    group_id: UUID,
    session_id: UUID,
    *,
    id: UUID | None = None,
    version: int = 0,
    mcp: bool = False,
    soft: bool = False,
    arg_position_ids: list[UUID] | None = None,
    arg_ids: list[UUID] | None = None,
    args_output_ids: list[UUID] | None = None,
    artifact_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    operation_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
) -> CreateToolDraftResponse:
    """Create a tool_drafts entry with optional connection table links."""
    draft_id = await conn.fetchval(
        """
        INSERT INTO tool_drafts_entry (id, group_id, session_id, version, active, mcp, generated)
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
        raise ValueError("Failed to create tool_drafts entry")

    connections: list[tuple[str, str, list[UUID]]] = [
        (
            "tool_drafts_arg_positions_connection",
            "arg_positions_id",
            arg_position_ids or [],
        ),
        ("tool_drafts_args_connection", "args_id", arg_ids or []),
        (
            "tool_drafts_args_outputs_connection",
            "args_outputs_id",
            args_output_ids or [],
        ),
        ("tool_drafts_artifacts_connection", "artifacts_id", artifact_ids or []),
        ("tool_drafts_departments_connection", "departments_id", department_ids or []),
        (
            "tool_drafts_descriptions_connection",
            "descriptions_id",
            description_ids or [],
        ),
        ("tool_drafts_flags_connection", "flags_id", flag_ids or []),
        ("tool_drafts_names_connection", "names_id", name_ids or []),
        ("tool_drafts_operations_connection", "operations_id", operation_ids or []),
        ("tool_drafts_profiles_connection", "profiles_id", profile_ids or []),
    ]

    for table, col, ids in connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (draft_id, {col}) VALUES ($1, $2)",
                draft_id,
                rid,
            )

    return CreateToolDraftResponse(id=draft_id)
