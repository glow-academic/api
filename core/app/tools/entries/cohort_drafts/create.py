"""Cohort drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.cohort_drafts.types import CreateCohortDraftResponse
from app.utils.cache.hedged_row import write_back_row


async def create_cohort_draft(
    conn: asyncpg.Connection,
    redis: Redis,
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
    row = await conn.fetchrow(
        """
        INSERT INTO cohort_drafts_entry (id, session_id, active, mcp, generated, name)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, true, $4)
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id, created_at, active
        """,
        session_id,
        not soft,
        mcp,
        name,
        id,
    )

    if row is None:
        raise ValueError("Failed to create cohort_drafts entry")

    draft_id = row["id"]
    created_at = row["created_at"]
    actual_active = row["active"]

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

    def _committed(ids: list[UUID] | None) -> list[str]:
        return [str(rid) for rid in (ids or [])]

    def _pending_only(ids: list[UUID] | None) -> list[str]:
        if soft:
            return [str(rid) for rid in (ids or [])]
        return [str(rid) for rid in (ids or []) if rid in _pending]

    fresh_row = {
        "id": str(draft_id),
        "created_at": created_at.isoformat(),
        "generated": True,
        "mcp": mcp,
        "active": actual_active,
        "session_id": str(session_id),
        "name": name,
        "department_ids": _committed(department_ids),
        "description_ids": _committed(description_ids),
        "flag_ids": _committed(flag_ids),
        "name_ids": _committed(name_ids),
        "profile_persona_ids": _committed(profile_persona_ids),
        "profile_ids": _committed(profile_ids),
        "simulation_availability_ids": _committed(simulation_availability_ids),
        "simulation_position_ids": _committed(simulation_position_ids),
        "simulation_ids": _committed(simulation_ids),
        "pending_department_ids": _pending_only(department_ids),
        "pending_description_ids": _pending_only(description_ids),
        "pending_flag_ids": _pending_only(flag_ids),
        "pending_name_ids": _pending_only(name_ids),
        "pending_profile_persona_ids": _pending_only(profile_persona_ids),
        "pending_profile_ids": _pending_only(profile_ids),
        "pending_simulation_availability_ids": _pending_only(simulation_availability_ids),
        "pending_simulation_position_ids": _pending_only(simulation_position_ids),
        "pending_simulation_ids": _pending_only(simulation_ids),
    }
    await write_back_row(
        redis,
        "cohort_drafts",
        draft_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateCohortDraftResponse(id=draft_id)
