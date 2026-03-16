"""Provider drafts entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.provider_drafts.create import create_provider_draft
from app.tools.entries.provider_drafts.get import get_provider_drafts
from app.tools.entries.provider_drafts.refresh import refresh_provider_drafts
from app.tools.entries.provider_drafts.search import search_provider_drafts


async def get_provider_drafts_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the provider_drafts entry."""
    mv_info = await get_mv_info(conn, "provider_drafts_mv")
    entry_table = await get_table_info(conn, "provider_drafts_entry")
    departments_connection = await get_table_info(
        conn, "provider_drafts_departments_connection"
    )
    descriptions_connection = await get_table_info(
        conn, "provider_drafts_descriptions_connection"
    )
    endpoints_connection = await get_table_info(
        conn, "provider_drafts_endpoints_connection"
    )
    flags_connection = await get_table_info(conn, "provider_drafts_flags_connection")
    keys_connection = await get_table_info(conn, "provider_drafts_keys_connection")
    names_connection = await get_table_info(conn, "provider_drafts_names_connection")
    profiles_connection = await get_table_info(
        conn, "provider_drafts_profiles_connection"
    )
    values_connection = await get_table_info(conn, "provider_drafts_values_connection")

    tables = [
        t
        for t in [
            entry_table,
            departments_connection,
            descriptions_connection,
            endpoints_connection,
            flags_connection,
            keys_connection,
            names_connection,
            profiles_connection,
            values_connection,
        ]
        if t is not None
    ]

    return DocsResponse(
        name="provider_drafts",
        type="entry",
        description=(
            "Provider draft artifacts with support for multiple resource connections. "
            "Each draft links to departments, descriptions, endpoints, flags, keys, names, profiles, "
            "and values via connection tables. "
            "Reads are served from the provider_drafts_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_provider_draft,
                description=(
                    "Creates a new provider draft, writing to provider_drafts_entry "
                    "and all relevant connection tables."
                ),
            ),
            get_operation_info(
                refresh_provider_drafts,
                description="Refreshes provider_drafts_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_provider_drafts,
                description="Batch retrieves provider drafts by IDs from provider_drafts_mv.",
            ),
            get_operation_info(
                search_provider_drafts,
                description="Filtered paginated search against provider_drafts_mv.",
            ),
        ],
    )
