"""Department artifact CREATE — tool layer."""

from uuid import UUID

import asyncpg

from app.infra.junctions import (
    insert_multi,
    insert_single,
)
from app.tools.artifacts.department.types import CreateDepartmentResponse

OWNER_COL = "department_id"

# (junction_table, resource_column)
SINGLE_JUNCTIONS: list[tuple[str, str]] = [
    ("department_names_junction", "names_id"),
    ("department_descriptions_junction", "descriptions_id"),
]

MULTI_JUNCTIONS: list[tuple[str, str]] = [
    ("department_departments_junction", "departments_id"),
    ("department_settings_junction", "settings_id"),
]


async def create_department(
    conn: asyncpg.Connection,
    *,
    id: UUID | None = None,
    name_id: UUID | None = None,
    description_id: UUID | None = None,
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    settings_ids: list[UUID] | None = None,
    active: bool | None = None,
    soft: bool = False,
    generated: bool = False,
    mcp: bool = False,
) -> CreateDepartmentResponse:
    """Create a department artifact with optional junction links."""
    is_active = not soft if active is None else active
    department_id: UUID = await conn.fetchval(
        """
        INSERT INTO department_artifact (id, active, generated, mcp)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3)
        RETURNING id
        """,
        is_active,
        generated,
        mcp,
        id,
    )

    # Single-select junctions
    single_vals = [name_id, description_id]
    for (table, col), val in zip(SINGLE_JUNCTIONS, single_vals):
        if val is not None:
            await insert_single(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=department_id,
                resource_col=col,
                resource_id=val,
                generated=generated,
                mcp=mcp,
            )

    # Multi-select junctions (simple)
    multi_vals = [department_ids, settings_ids]
    for (table, col), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals:
            await insert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=department_id,
                resource_col=col,
                resource_ids=vals,
                generated=generated,
                mcp=mcp,
            )

    # Flags
    if flag_ids:
        await insert_multi(
            conn,
            table="department_flags_junction",
            owner_col=OWNER_COL,
            owner_id=department_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            generated=generated,
            mcp=mcp,
        )

    return CreateDepartmentResponse(id=department_id)
