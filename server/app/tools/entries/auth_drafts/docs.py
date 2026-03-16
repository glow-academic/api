"""Auth drafts entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.auth_drafts.create import create_auth_draft
from app.tools.entries.auth_drafts.get import get_auth_drafts
from app.tools.entries.auth_drafts.refresh import refresh_auth_drafts
from app.tools.entries.auth_drafts.search import search_auth_drafts


async def get_auth_drafts_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the auth_drafts entry."""
    mv_info = await get_mv_info(conn, "auth_drafts_mv")
    entry_table = await get_table_info(conn, "auth_drafts_entry")
    departments_connection = await get_table_info(
        conn, "auth_drafts_departments_connection"
    )
    descriptions_connection = await get_table_info(
        conn, "auth_drafts_descriptions_connection"
    )
    flags_connection = await get_table_info(conn, "auth_drafts_flags_connection")
    items_connection = await get_table_info(conn, "auth_drafts_items_connection")
    names_connection = await get_table_info(conn, "auth_drafts_names_connection")
    profiles_connection = await get_table_info(conn, "auth_drafts_profiles_connection")
    protocols_connection = await get_table_info(
        conn, "auth_drafts_protocols_connection"
    )
    slugs_connection = await get_table_info(conn, "auth_drafts_slugs_connection")

    tables = [
        t
        for t in [
            entry_table,
            departments_connection,
            descriptions_connection,
            flags_connection,
            items_connection,
            names_connection,
            profiles_connection,
            protocols_connection,
            slugs_connection,
        ]
        if t is not None
    ]

    return DocsResponse(
        name="auth_drafts",
        type="entry",
        description=(
            "Auth draft artifacts with support for multiple resource connections. "
            "Each draft links to departments, descriptions, flags, items, names, profiles, "
            "protocols, and slugs via connection tables. "
            "Reads are served from the auth_drafts_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_auth_draft,
                description=(
                    "Creates a new auth draft, writing to auth_drafts_entry "
                    "and all relevant connection tables."
                ),
            ),
            get_operation_info(
                refresh_auth_drafts,
                description="Refreshes auth_drafts_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_auth_drafts,
                description="Batch retrieves auth drafts by IDs from auth_drafts_mv.",
            ),
            get_operation_info(
                search_auth_drafts,
                description="Filtered paginated search against auth_drafts_mv.",
            ),
        ],
    )
