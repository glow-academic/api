"""Invocation drafts entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.invocation_drafts.create import create_invocation_draft
from app.tools.entries.invocation_drafts.get import get_invocation_drafts
from app.tools.entries.invocation_drafts.refresh import (
    refresh_invocation_drafts,
)
from app.tools.entries.invocation_drafts.search import (
    search_invocation_drafts,
)


async def get_invocation_drafts_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the invocation_drafts entry."""
    mv_info = await get_mv_info(conn, "invocation_drafts_mv")
    entry_table = await get_table_info(conn, "invocation_drafts_entry")
    departments_connection = await get_table_info(
        conn, "invocation_drafts_departments_connection"
    )
    descriptions_connection = await get_table_info(
        conn, "invocation_drafts_descriptions_connection"
    )
    flags_connection = await get_table_info(conn, "invocation_drafts_flags_connection")
    keys_connection = await get_table_info(conn, "invocation_drafts_keys_connection")
    model_flags_connection = await get_table_info(
        conn, "invocation_drafts_model_flags_connection"
    )
    model_positions_connection = await get_table_info(
        conn, "invocation_drafts_model_positions_connection"
    )
    model_rubrics_connection = await get_table_info(
        conn, "invocation_drafts_model_rubrics_connection"
    )
    names_connection = await get_table_info(conn, "invocation_drafts_names_connection")
    profiles_connection = await get_table_info(
        conn, "invocation_drafts_profiles_connection"
    )
    reasoning_levels_connection = await get_table_info(
        conn, "invocation_drafts_reasoning_levels_connection"
    )
    temperature_levels_connection = await get_table_info(
        conn, "invocation_drafts_temperature_levels_connection"
    )
    voices_connection = await get_table_info(
        conn, "invocation_drafts_voices_connection"
    )

    tables = [
        t
        for t in [
            entry_table,
            departments_connection,
            descriptions_connection,
            flags_connection,
            keys_connection,
            model_flags_connection,
            model_positions_connection,
            model_rubrics_connection,
            names_connection,
            profiles_connection,
            reasoning_levels_connection,
            temperature_levels_connection,
            voices_connection,
        ]
        if t is not None
    ]

    return DocsResponse(
        name="invocation_drafts",
        type="entry",
        description=(
            "Invocation draft artifacts with support for multiple resource connections. "
            "Each draft links to departments, descriptions, flags, keys, model flags, model positions, "
            "model rubrics, names, profiles, reasoning levels, temperature levels, and voices "
            "via connection tables. "
            "Reads are served from the invocation_drafts_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_invocation_draft,
                description=(
                    "Creates a new invocation draft, writing to invocation_drafts_entry "
                    "and all relevant connection tables."
                ),
            ),
            get_operation_info(
                refresh_invocation_drafts,
                description="Refreshes invocation_drafts_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_invocation_drafts,
                description="Batch retrieves invocation drafts by IDs from invocation_drafts_mv.",
            ),
            get_operation_info(
                search_invocation_drafts,
                description="Filtered paginated search against invocation_drafts_mv.",
            ),
        ],
    )
