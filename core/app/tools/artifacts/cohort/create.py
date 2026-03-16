"""Cohort artifact CREATE — tool layer."""

from uuid import UUID

import asyncpg

from app.infra.junctions import (
    insert_multi,
    insert_single,
)
from app.tools.artifacts.cohort.types import CreateCohortResponse

OWNER_COL = "cohort_id"

# (junction_table, resource_column)
SINGLE_JUNCTIONS: list[tuple[str, str]] = [
    ("cohort_names_junction", "names_id"),
    ("cohort_descriptions_junction", "descriptions_id"),
]

MULTI_JUNCTIONS: list[tuple[str, str]] = [
    ("cohort_departments_junction", "departments_id"),
    ("cohort_profiles_junction", "profiles_id"),
    ("cohort_profile_personas_junction", "profile_personas_id"),
    ("cohort_simulations_junction", "simulations_id"),
    ("cohort_simulation_availability_junction", "simulation_availability_id"),
    ("cohort_simulation_positions_junction", "simulation_positions_id"),
    ("cohort_cohorts_junction", "cohorts_id"),
]


async def create_cohort(
    conn: asyncpg.Connection,
    *,
    id: UUID | None = None,
    name_id: UUID | None = None,
    description_id: UUID | None = None,
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    profile_persona_ids: list[UUID] | None = None,
    simulation_ids: list[UUID] | None = None,
    simulation_availability_ids: list[UUID] | None = None,
    simulation_position_ids: list[UUID] | None = None,
    cohort_ids: list[UUID] | None = None,
    active: bool | None = None,
    soft: bool = False,
    generated: bool = False,
    mcp: bool = False,
) -> CreateCohortResponse:
    """Create a cohort artifact with optional junction links."""
    is_active = not soft if active is None else active
    cohort_id: UUID = await conn.fetchval(
        """
        INSERT INTO cohort_artifact (id, active, generated, mcp)
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
                owner_id=cohort_id,
                resource_col=col,
                resource_id=val,
                generated=generated,
                mcp=mcp,
            )

    # Multi-select junctions (simple)
    multi_vals = [
        department_ids,
        profile_ids,
        profile_persona_ids,
        simulation_ids,
        simulation_availability_ids,
        simulation_position_ids,
        cohort_ids,
    ]
    for (table, col), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals:
            await insert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=cohort_id,
                resource_col=col,
                resource_ids=vals,
                generated=generated,
                mcp=mcp,
            )

    # Flags
    if flag_ids:
        await insert_multi(
            conn,
            table="cohort_flags_junction",
            owner_col=OWNER_COL,
            owner_id=cohort_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            generated=generated,
            mcp=mcp,
        )

    return CreateCohortResponse(id=cohort_id)
