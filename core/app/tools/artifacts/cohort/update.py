"""Cohort artifact UPDATE — tool layer.

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
from app.tools.artifacts.cohort.types import UpdateCohortResponse

_UNSET: Any = object()

OWNER_COL = "cohort_id"

# (junction_table, resource_column, pk_constraint)
SINGLE_JUNCTIONS: list[tuple[str, str, str]] = [
    ("cohort_names_junction", "names_id", "cohort_names_pkey"),
    ("cohort_descriptions_junction", "descriptions_id", "cohort_descriptions_pkey"),
]

MULTI_JUNCTIONS: list[tuple[str, str, str]] = [
    ("cohort_departments_junction", "departments_id", "cohort_departments_pkey"),
    ("cohort_profiles_junction", "profiles_id", "cohort_profiles_junction_pkey"),
    (
        "cohort_profile_personas_junction",
        "profile_personas_id",
        "cohort_profile_personas_junction_pkey",
    ),
    ("cohort_simulations_junction", "simulations_id", "cohort_simulations_pkey"),
    (
        "cohort_simulation_availability_junction",
        "simulation_availability_id",
        "cohort_simulation_availability_junction_pkey",
    ),
    (
        "cohort_simulation_positions_junction",
        "simulation_positions_id",
        "cohort_simulation_positions_pkey",
    ),
    ("cohort_cohorts_junction", "cohorts_id", "cohort_cohorts_junction_pkey"),
]


async def update_cohort(
    conn: asyncpg.Connection,
    cohort_id: UUID,
    *,
    # Single-select junctions (_UNSET = don't change)
    name_id: UUID | Any = _UNSET,
    description_id: UUID | Any = _UNSET,
    # Multi-select junctions (None = don't change, [] = remove all)
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    profile_persona_ids: list[UUID] | None = None,
    simulation_ids: list[UUID] | None = None,
    simulation_availability_ids: list[UUID] | None = None,
    simulation_position_ids: list[UUID] | None = None,
    cohort_ids: list[UUID] | None = None,
    # Base columns
    active: bool | Any = _UNSET,
    soft: bool = False,
    mcp: bool = False,
) -> UpdateCohortResponse:
    """Update a cohort artifact with efficient junction diffs."""
    # soft=True forces active=false regardless of the active parameter
    if soft:
        active = False

    # 1. Update artifact row
    if active is not _UNSET:
        await conn.execute(
            "UPDATE cohort_artifact SET updated_at = NOW(), active = $2, mcp = $3 "
            "WHERE id = $1",
            cohort_id,
            active,
            mcp,
        )
    else:
        await conn.execute(
            "UPDATE cohort_artifact SET updated_at = NOW(), mcp = $2 WHERE id = $1",
            cohort_id,
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
                owner_id=cohort_id,
                resource_col=col,
                resource_id=val,
                constraint=constraint,
                mcp=mcp,
            )

    # 3. Multi-select junctions (simple)
    multi_vals: list[list[UUID] | None] = [
        department_ids,
        profile_ids,
        profile_persona_ids,
        simulation_ids,
        simulation_availability_ids,
        simulation_position_ids,
        cohort_ids,
    ]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals is not None:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=cohort_id,
                resource_col=col,
                resource_ids=vals,
                constraint=constraint,
                mcp=mcp,
            )

    # 4. Flags
    if flag_ids is not None:
        await upsert_multi(
            conn,
            table="cohort_flags_junction",
            owner_col=OWNER_COL,
            owner_id=cohort_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            constraint="cohort_flags_pkey",
            mcp=mcp,
        )

    return UpdateCohortResponse(id=cohort_id)
