"""Home search — filtered/paginated query against home_mv."""

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.home.types import GetHomeResponse

MV_NAME = "home_mv"


async def search_homes(
    conn: asyncpg.Connection,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetHomeResponse]:
    """Search home entries from home_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT home_id, simulation_ids, cohort_ids, department_ids,
               profile_ids, chat_ids, scenario_ids, created_at, updated_at, active
        FROM {source}
        ORDER BY created_at DESC
        LIMIT $1 OFFSET $2
        """,
        limit,
        offset,
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
