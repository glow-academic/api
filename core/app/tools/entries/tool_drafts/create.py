"""Tool drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.tool_drafts.types import CreateToolDraftResponse


async def create_tool_draft(
    conn: asyncpg.Connection,
    session_id: UUID,
    *,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    name: str = "",
    arg_position_ids: list[UUID] | None = None,
    arg_ids: list[UUID] | None = None,
    args_output_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    permission_ids: list[UUID] | None = None,
    instruction_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    agent_ids: list[UUID] | None = None,
    pending_ids: set[UUID] | None = None,
) -> CreateToolDraftResponse:
    """Create a tool_drafts entry with optional connection table links."""
    draft_id = await conn.fetchval(
        """
        INSERT INTO tool_drafts_entry (id, session_id, active, mcp, generated, name)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, true, $4)
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id
        """,
        session_id,
        not soft,
        mcp,
        name,
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
        ("tool_drafts_departments_connection", "departments_id", department_ids or []),
        (
            "tool_drafts_descriptions_connection",
            "descriptions_id",
            description_ids or [],
        ),
        ("tool_drafts_flags_connection", "flags_id", flag_ids or []),
        ("tool_drafts_names_connection", "names_id", name_ids or []),
        ("tool_drafts_instructions_connection", "instructions_id", instruction_ids or []),
        ("tool_drafts_permissions_connection", "permissions_id", permission_ids or []),
        ("tool_drafts_profiles_connection", "profiles_id", profile_ids or []),
        ("tool_drafts_agents_connection", "agents_id", agent_ids or []),
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

    return CreateToolDraftResponse(id=draft_id)
