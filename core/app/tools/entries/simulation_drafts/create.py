"""Simulation drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.simulation_drafts.types import (
    CreateSimulationDraftResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_simulation_draft(
    conn: asyncpg.Connection,
    redis: Redis,
    session_id: UUID,
    *,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    name: str = "",
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
    row = await conn.fetchrow(
        """
        INSERT INTO simulation_drafts_entry (id, session_id, active, mcp, generated, name)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, true, $4)
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id, created_at, active, mcp
        """,
        session_id,
        not soft,
        mcp,
        name,
        id,
    )

    if row is None:
        raise ValueError("Failed to create simulation_drafts entry")
    draft_id = row["id"]
    created_at = row["created_at"]
    active_val = row["active"]
    mcp_val = row["mcp"]

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

    _pending_strs = {str(x) for x in _pending}

    def _active_list(ids: list[UUID]) -> list[str]:
        if soft:
            return []
        return [str(rid) for rid in ids if str(rid) not in _pending_strs]

    def _pending_list(ids: list[UUID]) -> list[str]:
        if soft:
            return [str(rid) for rid in ids]
        return [str(rid) for rid in ids if str(rid) in _pending_strs]

    fresh_row = {
        "id": str(draft_id),
        "created_at": created_at.isoformat(),
        "generated": True,
        "mcp": mcp_val,
        "active": active_val,
        "session_id": str(session_id),
        "name": name,
        "department_ids": _active_list(department_ids or []),
        "description_ids": _active_list(description_ids or []),
        "flag_ids": _active_list(flag_ids or []),
        "name_ids": _active_list(name_ids or []),
        "profile_ids": _active_list(profile_ids or []),
        "scenario_flag_ids": _active_list(scenario_flag_ids or []),
        "scenario_position_ids": _active_list(scenario_position_ids or []),
        "scenario_rubric_ids": _active_list(scenario_rubric_ids or []),
        "scenario_time_limit_ids": _active_list(scenario_time_limit_ids or []),
        "scenario_ids": _active_list(scenario_ids or []),
        "pending_department_ids": _pending_list(department_ids or []),
        "pending_description_ids": _pending_list(description_ids or []),
        "pending_flag_ids": _pending_list(flag_ids or []),
        "pending_name_ids": _pending_list(name_ids or []),
        "pending_scenario_flag_ids": _pending_list(scenario_flag_ids or []),
        "pending_scenario_position_ids": _pending_list(scenario_position_ids or []),
        "pending_scenario_rubric_ids": _pending_list(scenario_rubric_ids or []),
        "pending_scenario_time_limit_ids": _pending_list(scenario_time_limit_ids or []),
        "pending_scenario_ids": _pending_list(scenario_ids or []),
    }
    await write_back_row(
        redis,
        "simulation_drafts",
        draft_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateSimulationDraftResponse(id=draft_id)
