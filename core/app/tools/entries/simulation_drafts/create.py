"""Simulation drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.simulation_drafts.types import (
    CreateSimulationDraftResponse,
)


async def create_simulation_draft(
    conn: asyncpg.Connection,
    session_id: UUID,
    *,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    department_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    scenario_flag_ids: list[UUID] | None = None,
    scenario_position_ids: list[UUID] | None = None,
    scenario_rubric_ids: list[UUID] | None = None,
    scenario_time_limit_ids: list[UUID] | None = None,
    scenario_ids: list[UUID] | None = None,
    pending_ids: set[UUID] | None = None,
) -> CreateSimulationDraftResponse:
    """Create a simulation_drafts entry with optional connection table links."""
    draft_id = await conn.fetchval(
        """
        INSERT INTO simulation_drafts_entry (id, session_id, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, true)
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id
        """,
        session_id,
        not soft,
        mcp,
        id,
    )

    if draft_id is None:
        raise ValueError("Failed to create simulation_drafts entry")

    connections: list[tuple[str, str, list[UUID]]] = [
        (
            "simulation_drafts_departments_connection",
            "departments_id",
            department_ids or [],
        ),
        (
            "simulation_drafts_descriptions_connection",
            "descriptions_id",
            description_ids or [],
        ),
        ("simulation_drafts_flags_connection", "flags_id", flag_ids or []),
        ("simulation_drafts_names_connection", "names_id", name_ids or []),
        ("simulation_drafts_profiles_connection", "profiles_id", profile_ids or []),
        (
            "simulation_drafts_scenario_flags_connection",
            "scenario_flags_id",
            scenario_flag_ids or [],
        ),
        (
            "simulation_drafts_scenario_positions_connection",
            "scenario_positions_id",
            scenario_position_ids or [],
        ),
        (
            "simulation_drafts_scenario_rubrics_connection",
            "scenario_rubrics_id",
            scenario_rubric_ids or [],
        ),
        (
            "simulation_drafts_scenario_time_limits_connection",
            "scenario_time_limits_id",
            scenario_time_limit_ids or [],
        ),
        ("simulation_drafts_scenarios_connection", "scenarios_id", scenario_ids or []),
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

    return CreateSimulationDraftResponse(id=draft_id)
