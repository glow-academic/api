"""Simulation drafts entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.simulation_drafts.create import create_simulation_draft
from app.tools.entries.simulation_drafts.get import get_simulation_drafts
from app.tools.entries.simulation_drafts.refresh import (
    refresh_simulation_drafts,
)
from app.tools.entries.simulation_drafts.search import (
    search_simulation_drafts,
)


async def get_simulation_drafts_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the simulation_drafts entry."""
    mv_info = await get_mv_info(conn, "simulation_drafts_mv")
    entry_table = await get_table_info(conn, "simulation_drafts_entry")
    departments_connection = await get_table_info(
        conn, "simulation_drafts_departments_connection"
    )
    descriptions_connection = await get_table_info(
        conn, "simulation_drafts_descriptions_connection"
    )
    flags_connection = await get_table_info(conn, "simulation_drafts_flags_connection")
    names_connection = await get_table_info(conn, "simulation_drafts_names_connection")
    profiles_connection = await get_table_info(
        conn, "simulation_drafts_profiles_connection"
    )
    scenario_flags_connection = await get_table_info(
        conn, "simulation_drafts_scenario_flags_connection"
    )
    scenario_positions_connection = await get_table_info(
        conn, "simulation_drafts_scenario_positions_connection"
    )
    scenario_rubrics_connection = await get_table_info(
        conn, "simulation_drafts_scenario_rubrics_connection"
    )
    scenario_time_limits_connection = await get_table_info(
        conn, "simulation_drafts_scenario_time_limits_connection"
    )
    scenarios_connection = await get_table_info(
        conn, "simulation_drafts_scenarios_connection"
    )

    tables = [
        t
        for t in [
            entry_table,
            departments_connection,
            descriptions_connection,
            flags_connection,
            names_connection,
            profiles_connection,
            scenario_flags_connection,
            scenario_positions_connection,
            scenario_rubrics_connection,
            scenario_time_limits_connection,
            scenarios_connection,
        ]
        if t is not None
    ]

    return DocsResponse(
        name="simulation_drafts",
        type="entry",
        description=(
            "Simulation draft artifacts with support for multiple resource connections. "
            "Each draft links to departments, descriptions, flags, names, profiles, scenario flags, "
            "scenario positions, scenario rubrics, scenario time limits, and scenarios via connection tables. "
            "Reads are served from the simulation_drafts_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_simulation_draft,
                description=(
                    "Creates a new simulation draft, writing to simulation_drafts_entry "
                    "and all relevant connection tables."
                ),
            ),
            get_operation_info(
                refresh_simulation_drafts,
                description="Refreshes simulation_drafts_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_simulation_drafts,
                description="Batch retrieves simulation drafts by IDs from simulation_drafts_mv.",
            ),
            get_operation_info(
                search_simulation_drafts,
                description="Filtered paginated search against simulation_drafts_mv.",
            ),
        ],
    )
