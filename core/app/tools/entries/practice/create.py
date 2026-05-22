"""Practice CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.practice.types import CreatePracticeResponse
from app.utils.cache.hedged_row import write_back_row


async def create_practice(
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
) -> CreatePracticeResponse:
    """Create a practice entry with all connection tables."""
    row = await conn.fetchrow(
        """
        INSERT INTO practice_entry (id, session_id, "position", active, mcp, generated, start_time, end_time)
        VALUES (COALESCE($7, uuidv7()), $1, $2, $3, $4, true, $5, $6)
        RETURNING id, created_at, updated_at
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
        raise ValueError("Failed to create practice entry")
    practice_id = row["id"]
    actual_created_at = row["created_at"]
    actual_updated_at = row["updated_at"]

    for cohorts_id in cohorts_ids:
        await conn.execute(
            """
            INSERT INTO practice_cohorts_connection (practice_id, cohorts_id, generated)
            VALUES ($1, $2, true)
            """,
            practice_id,
            cohorts_id,
        )

    for departments_id in departments_ids:
        await conn.execute(
            """
            INSERT INTO practice_departments_connection (practice_id, departments_id, generated)
            VALUES ($1, $2, true)
            """,
            practice_id,
            departments_id,
        )

    for simulations_id in simulations_ids:
        await conn.execute(
            """
            INSERT INTO practice_simulations_connection (practice_id, simulations_id, generated)
            VALUES ($1, $2, true)
            """,
            practice_id,
            simulations_id,
        )

    for profiles_id in profiles_ids:
        await conn.execute(
            """
            INSERT INTO practice_profiles_connection (practice_id, profiles_id, generated)
            VALUES ($1, $2, true)
            """,
            practice_id,
            profiles_id,
        )

    for profile_personas_id in profile_personas_ids:
        await conn.execute(
            """
            INSERT INTO practice_profile_personas_connection (practice_id, profile_personas_id, generated)
            VALUES ($1, $2, true)
            """,
            practice_id,
            profile_personas_id,
        )

    for simulation_availability_id in simulation_availability_ids:
        await conn.execute(
            """
            INSERT INTO practice_simulation_availability_connection (practice_id, simulation_availability_id, generated)
            VALUES ($1, $2, true)
            """,
            practice_id,
            simulation_availability_id,
        )

    for simulation_positions_id in simulation_positions_ids:
        await conn.execute(
            """
            INSERT INTO practice_simulation_positions_connection (practice_id, simulation_positions_id, generated)
            VALUES ($1, $2, true)
            """,
            practice_id,
            simulation_positions_id,
        )

    # Cache row mirrors GET response shape. chat_ids/scenario_ids default
    # to [] — they accrue later via practice_chat_entry; cache self-heals on TTL.
    fresh_row = {
        "id": str(practice_id),
        "session_id": str(session_id),
        "simulation_ids": [str(s) for s in simulations_ids],
        "cohort_ids": [str(c) for c in cohorts_ids],
        "department_ids": [str(d) for d in departments_ids],
        "profile_ids": [str(p) for p in profiles_ids],
        "chat_ids": [],
        "scenario_ids": [],
        "created_at": actual_created_at.isoformat(),
        "updated_at": actual_updated_at.isoformat(),
        "active": not soft,
    }
    await write_back_row(
        redis,
        "practice",
        practice_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )

    return CreatePracticeResponse(id=practice_id)
