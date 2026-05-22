"""Tool drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.tool_drafts.types import CreateToolDraftResponse
from app.utils.cache.hedged_row import write_back_row


async def create_tool_draft(
    conn: asyncpg.Connection,
    redis: Redis,
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
    row = await conn.fetchrow(
        """
        INSERT INTO tool_drafts_entry (id, session_id, active, mcp, generated, name)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, true, $4)
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id, created_at, active, mcp
        """,
        session_id,
        not soft,
        mcp,
        name,
        id,
    )

    if row is None:
        raise ValueError("Failed to create tool_drafts entry")
    draft_id = row["id"]
    created_at = row["created_at"]
    active_val = row["active"]
    mcp_val = row["mcp"]

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

    _pending_strs = {str(x) for x in _pending}

    def _active_list(ids: list[UUID]) -> list[str]:
        if soft:
            return []
        return [str(rid) for rid in ids if str(rid) not in _pending_strs]

    def _pending_list(ids: list[UUID]) -> list[str]:
        if soft:
            return [str(rid) for rid in ids]
        return [str(rid) for rid in ids if str(rid) in _pending_strs]

    fresh_row = {
        "id": str(draft_id),
        "created_at": created_at.isoformat(),
        "generated": True,
        "mcp": mcp_val,
        "active": active_val,
        "session_id": str(session_id),
        "name": name,
        "arg_position_ids": _active_list(arg_position_ids or []),
        "arg_ids": _active_list(arg_ids or []),
        "args_output_ids": _active_list(args_output_ids or []),
        "department_ids": _active_list(department_ids or []),
        "description_ids": _active_list(description_ids or []),
        "flag_ids": _active_list(flag_ids or []),
        "name_ids": _active_list(name_ids or []),
        "instruction_ids": _active_list(instruction_ids or []),
        "permission_ids": _active_list(permission_ids or []),
        "profile_ids": _active_list(profile_ids or []),
        "agent_ids": _active_list(agent_ids or []),
        "pending_arg_position_ids": _pending_list(arg_position_ids or []),
        "pending_arg_ids": _pending_list(arg_ids or []),
        "pending_args_output_ids": _pending_list(args_output_ids or []),
        "pending_department_ids": _pending_list(department_ids or []),
        "pending_description_ids": _pending_list(description_ids or []),
        "pending_flag_ids": _pending_list(flag_ids or []),
        "pending_name_ids": _pending_list(name_ids or []),
        "pending_instruction_ids": _pending_list(instruction_ids or []),
        "pending_permission_ids": _pending_list(permission_ids or []),
        "pending_agent_ids": _pending_list(agent_ids or []),
    }
    await write_back_row(
        redis,
        "tool_drafts",
        draft_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateToolDraftResponse(id=draft_id)
