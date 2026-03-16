"""Field drafts entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.field_drafts.create import create_field_draft
from app.tools.entries.field_drafts.get import get_field_drafts
from app.tools.entries.field_drafts.refresh import refresh_field_drafts
from app.tools.entries.field_drafts.search import search_field_drafts


async def get_field_drafts_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the field_drafts entry."""
    mv_info = await get_mv_info(conn, "field_drafts_mv")
    entry_table = await get_table_info(conn, "field_drafts_entry")
    conditional_parameters_connection = await get_table_info(
        conn, "field_drafts_conditional_parameters_connection"
    )
    departments_connection = await get_table_info(
        conn, "field_drafts_departments_connection"
    )
    descriptions_connection = await get_table_info(
        conn, "field_drafts_descriptions_connection"
    )
    flags_connection = await get_table_info(conn, "field_drafts_flags_connection")
    names_connection = await get_table_info(conn, "field_drafts_names_connection")
    profiles_connection = await get_table_info(conn, "field_drafts_profiles_connection")

    tables = [
        t
        for t in [
            entry_table,
            conditional_parameters_connection,
            departments_connection,
            descriptions_connection,
            flags_connection,
            names_connection,
            profiles_connection,
        ]
        if t is not None
    ]

    return DocsResponse(
        name="field_drafts",
        type="entry",
        description=(
            "Field draft artifacts with support for multiple resource connections. "
            "Each draft links to conditional parameters, departments, descriptions, flags, names, "
            "and profiles via connection tables. "
            "Reads are served from the field_drafts_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_field_draft,
                description=(
                    "Creates a new field draft, writing to field_drafts_entry "
                    "and all relevant connection tables."
                ),
            ),
            get_operation_info(
                refresh_field_drafts,
                description="Refreshes field_drafts_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_field_drafts,
                description="Batch retrieves field drafts by IDs from field_drafts_mv.",
            ),
            get_operation_info(
                search_field_drafts,
                description="Filtered paginated search against field_drafts_mv.",
            ),
        ],
    )
