"""Department drafts entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.department_drafts.create import create_department_draft
from app.tools.entries.department_drafts.get import get_department_drafts
from app.tools.entries.department_drafts.refresh import (
    refresh_department_drafts,
)
from app.tools.entries.department_drafts.search import (
    search_department_drafts,
)


async def get_department_drafts_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the department_drafts entry."""
    mv_info = await get_mv_info(conn, "department_drafts_mv")
    entry_table = await get_table_info(conn, "department_drafts_entry")
    descriptions_connection = await get_table_info(
        conn, "department_drafts_descriptions_connection"
    )
    flags_connection = await get_table_info(conn, "department_drafts_flags_connection")
    names_connection = await get_table_info(conn, "department_drafts_names_connection")
    profiles_connection = await get_table_info(
        conn, "department_drafts_profiles_connection"
    )
    settings_connection = await get_table_info(
        conn, "department_drafts_settings_connection"
    )

    tables = [
        t
        for t in [
            entry_table,
            descriptions_connection,
            flags_connection,
            names_connection,
            profiles_connection,
            settings_connection,
        ]
        if t is not None
    ]

    return DocsResponse(
        name="department_drafts",
        type="entry",
        description=(
            "Department draft artifacts with support for multiple resource connections. "
            "Each draft links to descriptions, flags, names, profiles, and settings via connection tables. "
            "Reads are served from the department_drafts_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_department_draft,
                description=(
                    "Creates a new department draft, writing to department_drafts_entry "
                    "and all relevant connection tables."
                ),
            ),
            get_operation_info(
                refresh_department_drafts,
                description="Refreshes department_drafts_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_department_drafts,
                description="Batch retrieves department drafts by IDs from department_drafts_mv.",
            ),
            get_operation_info(
                search_department_drafts,
                description="Filtered paginated search against department_drafts_mv.",
            ),
        ],
    )
