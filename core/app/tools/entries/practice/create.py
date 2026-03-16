"""Practice CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.practice.types import CreatePracticeResponse


async def create_practice(
    conn: asyncpg.Connection,
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
    practice_id = await conn.fetchval(
        """
        INSERT INTO practice_entry (id, session_id, "position", active, mcp, generated, start_time, end_time)
        VALUES (COALESCE($7, uuidv7()), $1, $2, $3, $4, true, $5, $6)
        RETURNING id
        """,
        session_id,
        position,
        not soft,
        mcp,
        start_time,
        end_time,
        id,
    )

    if practice_id is None:
        raise ValueError("Failed to create practice entry")

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

    return CreatePracticeResponse(id=practice_id)
