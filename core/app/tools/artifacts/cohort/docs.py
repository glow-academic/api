"""Cohort artifact documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.artifacts.cohort.create import create_cohort
from app.tools.artifacts.cohort.delete import delete_cohorts
from app.tools.artifacts.cohort.get import get_cohorts
from app.tools.artifacts.cohort.search import search_cohorts
from app.tools.artifacts.cohort.update import update_cohort


async def get_cohort_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the cohort artifact."""
    artifact_table = await get_table_info(conn, "cohort_artifact")
    tables = [t for t in [artifact_table] if t is not None]

    return DocsResponse(
        name="cohort",
        type="artifact",
        description=(
            "Cohorts group learner profiles into simulation assignments. "
            "Each cohort links to resources (names, descriptions, departments, profiles, "
            "profile_personas, simulations, simulation_availability, simulation_positions) "
            "via junction tables."
        ),
        tables=tables,
        operations=[
            get_operation_info(
                create_cohort,
                description="Creates a new cohort artifact with optional resource links.",
            ),
            get_operation_info(
                update_cohort,
                description="Updates an existing cohort's resource links.",
            ),
            get_operation_info(
                get_cohorts,
                description="Batch retrieves cohorts by IDs with optional junction data.",
            ),
            get_operation_info(
                search_cohorts,
                description="Filtered paginated search returning matching cohort IDs.",
            ),
            get_operation_info(
                delete_cohorts,
                description="Deletes cohorts by IDs. Supports soft delete (active=false) or hard delete (cascade).",
            ),
        ],
    )
