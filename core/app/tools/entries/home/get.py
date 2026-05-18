"""home/get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.home.types import GetHomeResponse

MV_NAME = "home_mv"


async def get_homes(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetHomeResponse]:
    """Get home entries by IDs from home_mv."""
    if not ids:
        return []

    rows = await conn.fetch(
        f"""
        SELECT home_id, simulation_ids, cohort_ids, department_ids,
               profile_ids, chat_ids, scenario_ids, created_at, updated_at, active
        FROM {MV_NAME}
        WHERE home_id = ANY($1)
        """,
        ids,
    )

    return [
        GetHomeResponse(
            id=r["home_id"],
            simulation_ids=r["simulation_ids"],
            cohort_ids=r["cohort_ids"],
            department_ids=r["department_ids"],
            profile_ids=r["profile_ids"],
            chat_ids=r["chat_ids"],
            scenario_ids=r["scenario_ids"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            active=r["active"],
        )
        for r in rows
    ]
