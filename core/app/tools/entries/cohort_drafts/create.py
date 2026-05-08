"""Cohort drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.cohort_drafts.types import CreateCohortDraftResponse


async def create_cohort_draft(
    conn: asyncpg.Connection,
    session_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    name: str = "",
    department_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    profile_persona_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    simulation_availability_ids: list[UUID] | None = None,
    simulation_position_ids: list[UUID] | None = None,
    simulation_ids: list[UUID] | None = None,
    pending_ids: set[UUID] | None = None,
) -> CreateCohortDraftResponse:
    """Create a cohort_drafts entry with optional connection table links."""
    draft_id = await conn.fetchval(
        """
        INSERT INTO cohort_drafts_entry (id, session_id, active, mcp, generated, name)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, true, $4)
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id
        """,
        session_id,
        not soft,
        mcp,
        name,
        id,
    )

    if draft_id is None:
        raise ValueError("Failed to create cohort_drafts entry")

    connections: list[tuple[str, str, list[UUID]]] = [
        (
            "cohort_drafts_departments_connection",
            "departments_id",
            department_ids or [],
        ),
        (
            "cohort_drafts_descriptions_connection",
            "descriptions_id",
            description_ids or [],
        ),
        ("cohort_drafts_flags_connection", "flags_id", flag_ids or []),
        ("cohort_drafts_names_connection", "names_id", name_ids or []),
        (
            "cohort_drafts_profile_personas_connection",
            "profile_personas_id",
            profile_persona_ids or [],
        ),
        ("cohort_drafts_profiles_connection", "profiles_id", profile_ids or []),
        (
            "cohort_drafts_simulation_availability_connection",
            "simulation_availability_id",
            simulation_availability_ids or [],
        ),
        (
            "cohort_drafts_simulation_positions_connection",
            "simulation_positions_id",
            simulation_position_ids or [],
        ),
        (
            "cohort_drafts_simulations_connection",
            "simulations_id",
            simulation_ids or [],
        ),
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

    return CreateCohortDraftResponse(id=draft_id)
