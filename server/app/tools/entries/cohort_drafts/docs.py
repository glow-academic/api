"""Cohort drafts entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.cohort_drafts.create import create_cohort_draft
from app.tools.entries.cohort_drafts.get import get_cohort_drafts
from app.tools.entries.cohort_drafts.refresh import refresh_cohort_drafts
from app.tools.entries.cohort_drafts.search import search_cohort_drafts


async def get_cohort_drafts_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the cohort_drafts entry."""
    mv_info = await get_mv_info(conn, "cohort_drafts_mv")
    entry_table = await get_table_info(conn, "cohort_drafts_entry")
    departments_connection = await get_table_info(
        conn, "cohort_drafts_departments_connection"
    )
    descriptions_connection = await get_table_info(
        conn, "cohort_drafts_descriptions_connection"
    )
    flags_connection = await get_table_info(conn, "cohort_drafts_flags_connection")
    names_connection = await get_table_info(conn, "cohort_drafts_names_connection")
    profile_personas_connection = await get_table_info(
        conn, "cohort_drafts_profile_personas_connection"
    )
    profiles_connection = await get_table_info(
        conn, "cohort_drafts_profiles_connection"
    )
    simulation_availability_connection = await get_table_info(
        conn, "cohort_drafts_simulation_availability_connection"
    )
    simulation_positions_connection = await get_table_info(
        conn, "cohort_drafts_simulation_positions_connection"
    )
    simulations_connection = await get_table_info(
        conn, "cohort_drafts_simulations_connection"
    )

    tables = [
        t
        for t in [
            entry_table,
            departments_connection,
            descriptions_connection,
            flags_connection,
            names_connection,
            profile_personas_connection,
            profiles_connection,
            simulation_availability_connection,
            simulation_positions_connection,
            simulations_connection,
        ]
        if t is not None
    ]

    return DocsResponse(
        name="cohort_drafts",
        type="entry",
        description=(
            "Cohort draft artifacts with support for multiple resource connections. "
            "Each draft links to departments, descriptions, flags, names, profile personas, profiles, "
            "simulation availability, simulation positions, and simulations via connection tables. "
            "Reads are served from the cohort_drafts_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_cohort_draft,
                description=(
                    "Creates a new cohort draft, writing to cohort_drafts_entry "
                    "and all relevant connection tables."
                ),
            ),
            get_operation_info(
                refresh_cohort_drafts,
                description="Refreshes cohort_drafts_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_cohort_drafts,
                description="Batch retrieves cohort drafts by IDs from cohort_drafts_mv.",
            ),
            get_operation_info(
                search_cohort_drafts,
                description="Filtered paginated search against cohort_drafts_mv.",
            ),
        ],
    )
