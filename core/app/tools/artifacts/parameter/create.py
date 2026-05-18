"""Parameter artifact CREATE — tool layer.

Idempotent via ON CONFLICT on artifact + upsert_* for junctions.
Re-calling with the same id promotes a dormant artifact.
"""

from uuid import UUID

import asyncpg

from app.infra.junctions import (
    upsert_multi,
    upsert_single,
)
from app.tools.artifacts.parameter.types import CreateParameterResponse

OWNER_COL = "parameter_id"

# (junction_table, resource_column, pk_constraint)
SINGLE_JUNCTIONS: list[tuple[str, str, str]] = [
    ("parameter_names_junction", "names_id", "parameter_names_pkey"),
    ("parameter_descriptions_junction", "descriptions_id", "parameter_descriptions_pkey"),
]

MULTI_JUNCTIONS: list[tuple[str, str, str]] = [
    ("parameter_departments_junction", "departments_id", "parameter_departments_pkey"),
    ("parameter_fields_junction", "fields_id", "parameter_fields_pkey"),
    ("parameter_parameters_junction", "parameters_id", "parameter_parameters_junction_pkey"),
]


async def create_parameter(
    conn: asyncpg.Connection,
    *,
    id: UUID | None = None,
    name_id: UUID | None = None,
    description_id: UUID | None = None,
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    field_ids: list[UUID] | None = None,
    parameter_ids: list[UUID] | None = None,
    active: bool | None = None,
    soft: bool = False,
    generated: bool = False,
    mcp: bool = False,
) -> CreateParameterResponse:
    """Create a parameter artifact with optional junction links.

    Idempotent: if id is provided and already exists, ON CONFLICT promotes
    the artifact. Junction rows use existing upsert_single/upsert_multi.
    """
    is_active = not soft if active is None else active
    parameter_id: UUID = await conn.fetchval(
        """
        INSERT INTO parameter_artifact (id, active, generated, mcp)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3)
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id
        """,
        is_active,
        generated,
        mcp,
        id,
    )

    # Single-select junctions — upsert_single handles ON CONFLICT
    single_vals = [name_id, description_id]
    for (table, col, constraint), val in zip(SINGLE_JUNCTIONS, single_vals):
        if val is not None:
            await upsert_single(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=parameter_id,
                resource_col=col,
                resource_id=val,
                constraint=constraint,
                mcp=mcp,
                soft=soft,
            )

    # Multi-select junctions — upsert_multi handles ON CONFLICT
    multi_vals = [
        department_ids,
        field_ids,
        parameter_ids,
    ]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=parameter_id,
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
            table="parameter_flags_junction",
            owner_col=OWNER_COL,
            owner_id=parameter_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            constraint="parameter_flags_pkey",
            mcp=mcp,
            soft=soft,
        )

    return CreateParameterResponse(id=parameter_id)
