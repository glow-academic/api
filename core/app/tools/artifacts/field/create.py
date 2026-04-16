"""Field artifact CREATE — tool layer.

Idempotent via ON CONFLICT on artifact + upsert_* for junctions.
Re-calling with the same id promotes a dormant artifact.
"""

from uuid import UUID

import asyncpg

from app.infra.junctions import (
    upsert_multi,
    upsert_single,
)
from app.tools.artifacts.field.types import CreateFieldResponse

OWNER_COL = "field_id"

# (junction_table, resource_column, pk_constraint)
SINGLE_JUNCTIONS: list[tuple[str, str, str]] = [
    ("field_names_junction", "names_id", "field_names_pkey"),
    ("field_descriptions_junction", "descriptions_id", "field_descriptions_pkey"),
]

MULTI_JUNCTIONS: list[tuple[str, str, str]] = [
    ("field_departments_junction", "departments_id", "field_departments_pkey"),
    ("field_conditional_parameters_junction", "conditional_parameters_id", "field_conditional_parameters_junction_pkey"),
    ("field_fields_junction", "fields_id", "field_fields_junction_pkey"),
]


async def create_field(
    conn: asyncpg.Connection,
    *,
    id: UUID | None = None,
    name_id: UUID | None = None,
    description_id: UUID | None = None,
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    conditional_parameter_ids: list[UUID] | None = None,
    field_ids: list[UUID] | None = None,
    active: bool | None = None,
    soft: bool = False,
    generated: bool = False,
    mcp: bool = False,
) -> CreateFieldResponse:
    """Create a field artifact with optional junction links."""
    is_active = not soft if active is None else active
    field_id: UUID = await conn.fetchval(
        """
        INSERT INTO field_artifact (id, active, generated, mcp)
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
                owner_id=field_id,
                resource_col=col,
                resource_id=val,
                constraint=constraint,
                mcp=mcp,
                soft=soft,
            )

    # Multi-select junctions (simple)
    multi_vals = [department_ids, conditional_parameter_ids, field_ids]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=field_id,
                resource_col=col,
                resource_ids=vals,
                constraint=constraint,
                mcp=mcp,
                soft=soft,
            )

    # Flags
    if flag_ids:
        await upsert_multi(
            conn,
            table="field_flags_junction",
            owner_col=OWNER_COL,
            owner_id=field_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            constraint="field_flags_pkey",
            mcp=mcp,
            soft=soft,
        )

    return CreateFieldResponse(id=field_id)
