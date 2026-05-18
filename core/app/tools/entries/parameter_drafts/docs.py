"""Parameter drafts entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.parameter_drafts.create import create_parameter_draft
from app.tools.entries.parameter_drafts.get import get_parameter_drafts
from app.tools.entries.parameter_drafts.refresh import (
    refresh_parameter_drafts,
)
from app.tools.entries.parameter_drafts.search import search_parameter_drafts


async def get_parameter_drafts_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the parameter_drafts entry."""
    mv_info = await get_mv_info(conn, "parameter_drafts_mv")
    entry_table = await get_table_info(conn, "parameter_drafts_entry")
    departments_connection = await get_table_info(
        conn, "parameter_drafts_departments_connection"
    )
    descriptions_connection = await get_table_info(
        conn, "parameter_drafts_descriptions_connection"
    )
    fields_connection = await get_table_info(conn, "parameter_drafts_fields_connection")
    flags_connection = await get_table_info(conn, "parameter_drafts_flags_connection")
    names_connection = await get_table_info(conn, "parameter_drafts_names_connection")
    profiles_connection = await get_table_info(
        conn, "parameter_drafts_profiles_connection"
    )

    tables = [
        t
        for t in [
            entry_table,
            departments_connection,
            descriptions_connection,
            fields_connection,
            flags_connection,
            names_connection,
            profiles_connection,
        ]
        if t is not None
    ]

    return DocsResponse(
        name="parameter_drafts",
        type="entry",
        description=(
            "Parameter draft artifacts with support for multiple resource connections. "
            "Each draft links to departments, descriptions, fields, flags, names, and profiles "
            "via connection tables. "
            "Reads are served from the parameter_drafts_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_parameter_draft,
                description=(
                    "Creates a new parameter draft, writing to parameter_drafts_entry "
                    "and all relevant connection tables."
                ),
            ),
            get_operation_info(
                refresh_parameter_drafts,
                description="Refreshes parameter_drafts_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_parameter_drafts,
                description="Batch retrieves parameter drafts by IDs from parameter_drafts_mv.",
            ),
            get_operation_info(
                search_parameter_drafts,
                description="Filtered paginated search against parameter_drafts_mv.",
            ),
        ],
    )
