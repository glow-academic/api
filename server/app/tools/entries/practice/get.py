"""practice/get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.practice.types import GetPracticeResponse

MV_NAME = "practice_mv"


async def get_practices(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetPracticeResponse]:
    """Get practice entries by IDs from practice_mv."""
    if not ids:
        return []

    rows = await conn.fetch(
        f"""
        SELECT practice_id, simulation_ids, cohort_ids, department_ids,
               profile_ids, chat_ids, scenario_ids,
               created_at, updated_at, active
        FROM {MV_NAME}
        WHERE practice_id = ANY($1)
        """,
        ids,
    )

    return [
        GetPracticeResponse(
            id=r["practice_id"],
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
