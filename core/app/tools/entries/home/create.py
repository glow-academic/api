"""Home CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.home.types import CreateHomeResponse
from app.utils.cache.hedged_row import write_back_row


async def create_home(
    conn: asyncpg.Connection,
    redis: Redis,
    session_id: UUID,
    cohorts_ids: list[UUID],
    departments_ids: list[UUID],
    simulations_ids: list[UUID],
    profiles_ids: list[UUID],
    profile_personas_ids: list[UUID],
    simulation_availability_ids: list[UUID],
    simulation_positions_ids: list[UUID],
    id: UUID | None = None,
    position: int = 0,
    mcp: bool = False,
    soft: bool = False,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> CreateHomeResponse:
    """Create a home entry with all connection tables."""
    row = await conn.fetchrow(
        """
        INSERT INTO home_entry (id, session_id, "position", active, mcp, generated, start_time, end_time)
        VALUES (COALESCE($7, uuidv7()), $1, $2, $3, $4, true, $5, $6)
        RETURNING id, created_at, active
        """,
        session_id,
        position,
        not soft,
        mcp,
        start_time,
        end_time,
        id,
    )

    if row is None:
        raise ValueError("Failed to create home entry")
    home_id = row["id"]
    created_at = row["created_at"]
    active_val = row["active"]

    # Connection tables
    for cohorts_id in cohorts_ids:
        await conn.execute(
            """
            INSERT INTO home_cohorts_connection (home_id, cohorts_id, generated)
            VALUES ($1, $2, true)
            """,
            home_id,
            cohorts_id,
        )

    for departments_id in departments_ids:
        await conn.execute(
            """
            INSERT INTO home_departments_connection (home_id, departments_id, generated)
            VALUES ($1, $2, true)
            """,
            home_id,
            departments_id,
        )

    for simulations_id in simulations_ids:
        await conn.execute(
            """
            INSERT INTO home_simulations_connection (home_id, simulations_id, generated)
            VALUES ($1, $2, true)
            """,
            home_id,
            simulations_id,
        )

    for profiles_id in profiles_ids:
        await conn.execute(
            """
            INSERT INTO home_profiles_connection (home_id, profiles_id, generated)
            VALUES ($1, $2, true)
            """,
            home_id,
            profiles_id,
        )

    for profile_personas_id in profile_personas_ids:
        await conn.execute(
            """
            INSERT INTO home_profile_personas_connection (home_id, profile_personas_id, generated)
            VALUES ($1, $2, true)
            """,
            home_id,
            profile_personas_id,
        )

    for simulation_availability_id in simulation_availability_ids:
        await conn.execute(
            """
            INSERT INTO home_simulation_availability_connection (home_id, simulation_availability_id, generated)
            VALUES ($1, $2, true)
            """,
            home_id,
            simulation_availability_id,
        )

    for simulation_positions_id in simulation_positions_ids:
        await conn.execute(
            """
            INSERT INTO home_simulation_positions_connection (home_id, simulation_positions_id, generated)
            VALUES ($1, $2, true)
            """,
            home_id,
            simulation_positions_id,
        )

    # Write-back cache row. chat_ids and scenario_ids are sourced
    # from joins in home_mv that aren't known at create-time; empty
    # at creation, populated via MV refresh.
    fresh_row = {
        "id": str(home_id),
        "simulation_ids": [str(s) for s in simulations_ids],
        "cohort_ids": [str(c) for c in cohorts_ids],
        "department_ids": [str(d) for d in departments_ids],
        "profile_ids": [str(p) for p in profiles_ids],
        "chat_ids": [],
        "scenario_ids": [],
        "created_at": created_at.isoformat(),
        "updated_at": created_at.isoformat(),
        "active": active_val,
    }
    await write_back_row(
        redis,
        "home",
        home_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateHomeResponse(id=home_id)
