"""Rubric artifact UPDATE — tool layer.

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
from app.tools.artifacts.rubric.types import UpdateRubricResponse

_UNSET: Any = object()

OWNER_COL = "rubric_id"

# (junction_table, resource_column, pk_constraint)
SINGLE_JUNCTIONS: list[tuple[str, str, str]] = [
    ("rubric_names_junction", "names_id", "rubric_names_pkey"),
    ("rubric_descriptions_junction", "descriptions_id", "rubric_descriptions_pkey"),
]

MULTI_JUNCTIONS: list[tuple[str, str, str]] = [
    ("rubric_departments_junction", "departments_id", "rubric_departments_pkey"),
    ("rubric_points_junction", "points_id", "rubric_points_pkey"),
    (
        "rubric_standard_groups_junction",
        "standard_groups_id",
        "rubric_standard_groups_pkey",
    ),
    ("rubric_standards_junction", "standards_id", "rubric_standards_pkey"),
    ("rubric_rubrics_junction", "rubrics_id", "rubric_rubrics_junction_pkey"),
]


async def update_rubric(
    conn: asyncpg.Connection,
    rubric_id: UUID,
    *,
    # Single-select junctions (_UNSET = don't change)
    name_id: UUID | Any = _UNSET,
    description_id: UUID | Any = _UNSET,
    # Multi-select junctions (None = don't change, [] = remove all)
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    point_ids: list[UUID] | None = None,
    standard_group_ids: list[UUID] | None = None,
    standard_ids: list[UUID] | None = None,
    rubric_ids: list[UUID] | None = None,
    # Base columns
    active: bool | Any = _UNSET,
    soft: bool = False,
    mcp: bool = False,
) -> UpdateRubricResponse:
    """Update a rubric artifact with efficient junction diffs."""
    # soft=True forces active=false regardless of the active parameter
    if soft:
        active = False

    # 1. Update artifact row
    if active is not _UNSET:
        await conn.execute(
            "UPDATE rubric_artifact SET updated_at = NOW(), active = $2, mcp = $3 "
            "WHERE id = $1",
            rubric_id,
            active,
            mcp,
        )
    else:
        await conn.execute(
            "UPDATE rubric_artifact SET updated_at = NOW(), mcp = $2 WHERE id = $1",
            rubric_id,
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
                owner_id=rubric_id,
                resource_col=col,
                resource_id=val,
                constraint=constraint,
                mcp=mcp,
            )

    # 3. Multi-select junctions (simple)
    multi_vals: list[list[UUID] | None] = [
        department_ids,
        point_ids,
        standard_group_ids,
        standard_ids,
        rubric_ids,
    ]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals is not None:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=rubric_id,
                resource_col=col,
                resource_ids=vals,
                constraint=constraint,
                mcp=mcp,
            )

    # 4. Flags
    if flag_ids is not None:
        await upsert_multi(
            conn,
            table="rubric_flags_junction",
            owner_col=OWNER_COL,
            owner_id=rubric_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            constraint="rubric_flags_pkey",
            mcp=mcp,
        )

    return UpdateRubricResponse(id=rubric_id)
