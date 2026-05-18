"""Rubric artifact CREATE — tool layer."""

from uuid import UUID

import asyncpg

from app.infra.junctions import (
    upsert_multi,
    upsert_single,
)
from app.tools.artifacts.rubric.types import CreateRubricResponse

OWNER_COL = "rubric_id"

# (junction_table, resource_column, pk_constraint)
SINGLE_JUNCTIONS: list[tuple[str, str, str]] = [
    ("rubric_names_junction", "names_id", "rubric_names_pkey"),
    ("rubric_descriptions_junction", "descriptions_id", "rubric_descriptions_pkey"),
]

MULTI_JUNCTIONS: list[tuple[str, str, str]] = [
    ("rubric_departments_junction", "departments_id", "rubric_departments_pkey"),
    ("rubric_points_junction", "points_id", "rubric_points_pkey"),
    ("rubric_standard_groups_junction", "standard_groups_id", "rubric_standard_groups_pkey"),
    ("rubric_standards_junction", "standards_id", "rubric_standards_pkey"),
    ("rubric_rubrics_junction", "rubrics_id", "rubric_rubrics_junction_pkey"),
]


async def create_rubric(
    conn: asyncpg.Connection,
    *,
    id: UUID | None = None,
    name_id: UUID | None = None,
    description_id: UUID | None = None,
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    point_ids: list[UUID] | None = None,
    standard_group_ids: list[UUID] | None = None,
    standard_ids: list[UUID] | None = None,
    rubric_ids: list[UUID] | None = None,
    active: bool | None = None,
    soft: bool = False,
    generated: bool = False,
    mcp: bool = False,
) -> CreateRubricResponse:
    """Create a rubric artifact with optional junction links."""
    is_active = not soft if active is None else active
    rubric_id: UUID = await conn.fetchval(
        """
        INSERT INTO rubric_artifact (id, active, generated, mcp)
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
                owner_id=rubric_id,
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
        point_ids,
        standard_group_ids,
        standard_ids,
        rubric_ids,
    ]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=rubric_id,
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
            table="rubric_flags_junction",
            owner_col=OWNER_COL,
            owner_id=rubric_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            constraint="rubric_flags_pkey",
            generated=generated,
            mcp=mcp,
            soft=soft,
        )

    return CreateRubricResponse(id=rubric_id)
