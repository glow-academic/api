"""Eval drafts entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.eval_drafts.create import create_eval_draft
from app.tools.entries.eval_drafts.get import get_eval_drafts
from app.tools.entries.eval_drafts.refresh import refresh_eval_drafts
from app.tools.entries.eval_drafts.search import search_eval_drafts


async def get_eval_drafts_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the eval_drafts entry."""
    mv_info = await get_mv_info(conn, "eval_drafts_mv")
    entry_table = await get_table_info(conn, "eval_drafts_entry")
    departments_connection = await get_table_info(
        conn, "eval_drafts_departments_connection"
    )
    descriptions_connection = await get_table_info(
        conn, "eval_drafts_descriptions_connection"
    )
    flags_connection = await get_table_info(conn, "eval_drafts_flags_connection")
    models_connection = await get_table_info(conn, "eval_drafts_models_connection")
    names_connection = await get_table_info(conn, "eval_drafts_names_connection")
    profiles_connection = await get_table_info(conn, "eval_drafts_profiles_connection")
    rubrics_connection = await get_table_info(conn, "eval_drafts_rubrics_connection")

    tables = [
        t
        for t in [
            entry_table,
            departments_connection,
            descriptions_connection,
            flags_connection,
            models_connection,
            names_connection,
            profiles_connection,
            rubrics_connection,
        ]
        if t is not None
    ]

    return DocsResponse(
        name="eval_drafts",
        type="entry",
        description=(
            "Eval draft artifacts with support for multiple resource connections. "
            "Each draft links to departments, descriptions, flags, models, names, profiles, "
            "and rubrics via connection tables. "
            "Reads are served from the eval_drafts_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_eval_draft,
                description=(
                    "Creates a new eval draft, writing to eval_drafts_entry "
                    "and all relevant connection tables."
                ),
            ),
            get_operation_info(
                refresh_eval_drafts,
                description="Refreshes eval_drafts_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_eval_drafts,
                description="Batch retrieves eval drafts by IDs from eval_drafts_mv.",
            ),
            get_operation_info(
                search_eval_drafts,
                description="Filtered paginated search against eval_drafts_mv.",
            ),
        ],
    )
