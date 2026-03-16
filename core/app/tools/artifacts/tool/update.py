"""Tool artifact UPDATE — tool layer.

Efficient junction updates: only deactivate removed IDs, upsert new ones,
and touch (updated_at) unchanged ones.
"""

from typing import Any
from uuid import UUID

import asyncpg

from app.infra.junctions import (
    upsert_multi,
    upsert_single,
)
from app.tools.artifacts.tool.types import UpdateToolResponse

_UNSET: Any = object()

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
    ("tool_artifacts_junction", "artifacts_id", "tool_artifacts_junction_pkey"),
    ("tool_operations_junction", "operations_id", "tool_operations_pkey"),
    ("tool_tools_junction", "tools_id", "tool_tools_junction_pkey"),
]


async def update_tool(
    conn: asyncpg.Connection,
    tool_id: UUID,
    *,
    # Single-select junctions (_UNSET = don't change)
    name_id: UUID | Any = _UNSET,
    description_id: UUID | Any = _UNSET,
    # Multi-select junctions (None = don't change, [] = remove all)
    department_ids: list[UUID] | None = None,
    arg_positions_ids: list[UUID] | None = None,
    args_ids: list[UUID] | None = None,
    args_outputs_ids: list[UUID] | None = None,
    artifact_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    operation_ids: list[UUID] | None = None,
    tool_ids: list[UUID] | None = None,
    # Base columns
    active: bool | Any = _UNSET,
    soft: bool = False,
    mcp: bool = False,
) -> UpdateToolResponse:
    """Update a tool artifact with efficient junction diffs."""
    # soft=True forces active=false regardless of the active parameter
    if soft:
        active = False

    # 1. Update artifact row
    if active is not _UNSET:
        await conn.execute(
            "UPDATE tool_artifact SET updated_at = NOW(), active = $2, mcp = $3 "
            "WHERE id = $1",
            tool_id,
            active,
            mcp,
        )
    else:
        await conn.execute(
            "UPDATE tool_artifact SET updated_at = NOW(), mcp = $2 WHERE id = $1",
            tool_id,
            mcp,
        )

    # 2. Single-select junctions
    single_vals = [name_id, description_id]
    for (table, col, constraint), val in zip(SINGLE_JUNCTIONS, single_vals):
        if val is not _UNSET:
            await upsert_single(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=tool_id,
                resource_col=col,
                resource_id=val,
                constraint=constraint,
                mcp=mcp,
            )

    # 3. Multi-select junctions (simple)
    multi_vals: list[list[UUID] | None] = [
        department_ids,
        arg_positions_ids,
        args_ids,
        args_outputs_ids,
        artifact_ids,
        operation_ids,
        tool_ids,
    ]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals is not None:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=tool_id,
                resource_col=col,
                resource_ids=vals,
                constraint=constraint,
                mcp=mcp,
            )

    # 4. Flags
    if flag_ids is not None:
        await upsert_multi(
            conn,
            table="tool_flags_junction",
            owner_col=OWNER_COL,
            owner_id=tool_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            constraint="tool_flags_pkey",
            mcp=mcp,
        )

    return UpdateToolResponse(id=tool_id)
