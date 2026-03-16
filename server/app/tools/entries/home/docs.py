"""Home entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.home.create import create_home
from app.tools.entries.home.get import get_homes
from app.tools.entries.home.search import search_homes


async def get_home_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the home entry."""
    mv_info = await get_mv_info(conn, "home_mv")
    entry_table = await get_table_info(conn, "home_entry")
    cohorts_connection = await get_table_info(conn, "home_cohorts_connection")
    departments_connection = await get_table_info(conn, "home_departments_connection")
    simulations_connection = await get_table_info(conn, "home_simulations_connection")
    profiles_connection = await get_table_info(conn, "home_profiles_connection")
    profile_personas_connection = await get_table_info(
        conn, "home_profile_personas_connection"
    )
    simulation_availability_connection = await get_table_info(
        conn, "home_simulation_availability_connection"
    )
    simulation_positions_connection = await get_table_info(
        conn, "home_simulation_positions_connection"
    )

    tables = [
        t
        for t in [
            entry_table,
            cohorts_connection,
            departments_connection,
            simulations_connection,
            profiles_connection,
            profile_personas_connection,
            simulation_availability_connection,
            simulation_positions_connection,
        ]
        if t is not None
    ]

    return DocsResponse(
        name="home",
        type="entry",
        description=(
            "Home entries provide the dashboard context for users, linking cohorts, departments, simulations, "
            "profiles, and personas. Each home entry connects multiple resource types via connection tables. "
            "Reads are served from the home_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_home,
                description=(
                    "Creates a new home entry with connections to cohorts, departments, simulations, "
                    "profiles, personas, and simulation availability/positions."
                ),
            ),
            get_operation_info(
                get_homes,
                description="Batch retrieves home entries by IDs from home_mv with aggregated resource IDs.",
            ),
            get_operation_info(
                search_homes,
                description="Filtered paginated search against home_mv.",
            ),
        ],
    )
