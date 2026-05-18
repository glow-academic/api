"""Practice entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.practice.create import create_practice
from app.tools.entries.practice.get import get_practices
from app.tools.entries.practice.refresh import refresh_practice
from app.tools.entries.practice.search import search_practices


async def get_practice_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the practice entry."""
    mv_info = await get_mv_info(conn, "practice_mv")
    entry_table = await get_table_info(conn, "practice_entry")
    connection_tables = [
        await get_table_info(conn, "practice_cohorts_connection"),
        await get_table_info(conn, "practice_departments_connection"),
        await get_table_info(conn, "practice_profiles_connection"),
        await get_table_info(conn, "practice_profile_personas_connection"),
        await get_table_info(conn, "practice_simulations_connection"),
        await get_table_info(conn, "practice_simulation_availability_connection"),
        await get_table_info(conn, "practice_simulation_positions_connection"),
    ]

    tables = [t for t in [entry_table] + connection_tables if t is not None]

    return DocsResponse(
        name="practice",
        type="entry",
        description=(
            "Practice entries track simulated practice sessions with cohorts, departments, "
            "profiles, personas, simulations, and availability windows. "
            "Each practice links to multiple resources via connection tables. "
            "Reads are served from the practice_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_practice,
                description=(
                    "Creates a new practice entry with connections to cohorts, departments, "
                    "profiles, personas, simulations, and availability."
                ),
            ),
            get_operation_info(
                refresh_practice,
                description="Refreshes practice_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_practices,
                description="Batch retrieves practice entries by IDs from practice_mv.",
            ),
            get_operation_info(
                search_practices,
                description="Filtered paginated search against practice_mv.",
            ),
        ],
    )
