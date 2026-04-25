"""Tool artifact CREATE — tool layer."""

from uuid import UUID

import asyncpg

from app.infra.junctions import (
    upsert_multi,
    upsert_single,
)
from app.tools.artifacts.tool.types import CreateToolResponse

OWNER_COL = "tool_id"

# (junction_table, resource_column, pk_constraint)
SINGLE_JUNCTIONS: list[tuple[str, str, str]] = [
    ("tool_names_junction", "names_id", "tool_names_pkey"),
    ("tool_descriptions_junction", "descriptions_id", "tool_descriptions_pkey"),
]

MULTI_JUNCTIONS: list[tuple[str, str, str]] = [
    ("tool_departments_junction", "departments_id", "tool_departments_pkey"),
    (
        "tool_arg_positions_junction",
        "arg_positions_id",
        "tool_arg_positions_junction_pkey",
    ),
    ("tool_args_junction", "args_id", "tool_args_pkey"),
    ("tool_args_outputs_junction", "args_outputs_id", "tool_args_outputs_pkey"),
    ("tool_permissions_junction", "permissions_id", "tool_permissions_junction_pkey"),
    (
        "tool_instructions_junction",
        "instructions_id",
        "tool_instructions_junction_pkey",
    ),
    ("tool_tools_junction", "tools_id", "tool_tools_junction_pkey"),
]


async def create_tool(
    conn: asyncpg.Connection,
    *,
    id: UUID | None = None,
    name_id: UUID | None = None,
    description_id: UUID | None = None,
    department_ids: list[UUID] | None = None,
    arg_positions_ids: list[UUID] | None = None,
    args_ids: list[UUID] | None = None,
    args_outputs_ids: list[UUID] | None = None,
    permission_ids: list[UUID] | None = None,
    instruction_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    tool_ids: list[UUID] | None = None,
    active: bool | None = None,
    soft: bool = False,
    generated: bool = False,
    mcp: bool = False,
) -> CreateToolResponse:
    """Create a tool artifact with optional junction links."""
    is_active = not soft if active is None else active
    tool_id: UUID = await conn.fetchval(
        """
        INSERT INTO tool_artifact (id, active, generated, mcp)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3)
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id
        """,
        is_active,
        generated,
        mcp,
        id,
    )

    # Single-select junctions
    single_vals = [name_id, description_id]
    for (table, col, constraint), val in zip(SINGLE_JUNCTIONS, single_vals):
        if val is not None:
            await upsert_single(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=tool_id,
                resource_col=col,
                resource_id=val,
                constraint=constraint,
                generated=generated,
                mcp=mcp,
                soft=soft,
            )

    # Multi-select junctions (simple)
    multi_vals = [
        department_ids,
        arg_positions_ids,
        args_ids,
        args_outputs_ids,
        permission_ids,
        instruction_ids,
        tool_ids,
    ]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=tool_id,
                resource_col=col,
                resource_ids=vals,
                constraint=constraint,
                generated=generated,
                mcp=mcp,
                soft=soft,
            )

    # Flags
    if flag_ids:
        await upsert_multi(
            conn,
            table="tool_flags_junction",
            owner_col=OWNER_COL,
            owner_id=tool_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            constraint="tool_flags_pkey",
            generated=generated,
            mcp=mcp,
            soft=soft,
        )

    return CreateToolResponse(id=tool_id)
