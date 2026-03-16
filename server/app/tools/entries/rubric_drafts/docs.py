"""Rubric drafts entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.rubric_drafts.create import create_rubric_draft
from app.tools.entries.rubric_drafts.get import get_rubric_drafts
from app.tools.entries.rubric_drafts.refresh import refresh_rubric_drafts
from app.tools.entries.rubric_drafts.search import search_rubric_drafts


async def get_rubric_drafts_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the rubric_drafts entry."""
    mv_info = await get_mv_info(conn, "rubric_drafts_mv")
    entry_table = await get_table_info(conn, "rubric_drafts_entry")
    departments_connection = await get_table_info(
        conn, "rubric_drafts_departments_connection"
    )
    descriptions_connection = await get_table_info(
        conn, "rubric_drafts_descriptions_connection"
    )
    flags_connection = await get_table_info(conn, "rubric_drafts_flags_connection")
    names_connection = await get_table_info(conn, "rubric_drafts_names_connection")
    points_connection = await get_table_info(conn, "rubric_drafts_points_connection")
    profiles_connection = await get_table_info(
        conn, "rubric_drafts_profiles_connection"
    )
    standard_groups_connection = await get_table_info(
        conn, "rubric_drafts_standard_groups_connection"
    )
    standards_connection = await get_table_info(
        conn, "rubric_drafts_standards_connection"
    )

    tables = [
        t
        for t in [
            entry_table,
            departments_connection,
            descriptions_connection,
            flags_connection,
            names_connection,
            points_connection,
            profiles_connection,
            standard_groups_connection,
            standards_connection,
        ]
        if t is not None
    ]

    return DocsResponse(
        name="rubric_drafts",
        type="entry",
        description=(
            "Rubric draft artifacts with support for multiple resource connections. "
            "Each draft links to departments, descriptions, flags, names, points, profiles, "
            "standard groups, and standards via connection tables. "
            "Reads are served from the rubric_drafts_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_rubric_draft,
                description=(
                    "Creates a new rubric draft, writing to rubric_drafts_entry "
                    "and all relevant connection tables."
                ),
            ),
            get_operation_info(
                refresh_rubric_drafts,
                description="Refreshes rubric_drafts_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_rubric_drafts,
                description="Batch retrieves rubric drafts by IDs from rubric_drafts_mv.",
            ),
            get_operation_info(
                search_rubric_drafts,
                description="Filtered paginated search against rubric_drafts_mv.",
            ),
        ],
    )
