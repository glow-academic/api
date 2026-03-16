"""Setting drafts entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.setting_drafts.create import create_setting_draft
from app.tools.entries.setting_drafts.get import get_setting_drafts
from app.tools.entries.setting_drafts.refresh import refresh_setting_drafts
from app.tools.entries.setting_drafts.search import search_setting_drafts


async def get_setting_drafts_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the setting_drafts entry."""
    mv_info = await get_mv_info(conn, "setting_drafts_mv")
    entry_table = await get_table_info(conn, "setting_drafts_entry")
    agents_connection = await get_table_info(conn, "setting_drafts_agents_connection")
    auth_item_keys_connection = await get_table_info(
        conn, "setting_drafts_auth_item_keys_connection"
    )
    auths_connection = await get_table_info(conn, "setting_drafts_auths_connection")
    colors_connection = await get_table_info(conn, "setting_drafts_colors_connection")
    departments_connection = await get_table_info(
        conn, "setting_drafts_departments_connection"
    )
    descriptions_connection = await get_table_info(
        conn, "setting_drafts_descriptions_connection"
    )
    flags_connection = await get_table_info(conn, "setting_drafts_flags_connection")
    items_connection = await get_table_info(conn, "setting_drafts_items_connection")
    names_connection = await get_table_info(conn, "setting_drafts_names_connection")
    profiles_connection = await get_table_info(
        conn, "setting_drafts_profiles_connection"
    )
    provider_keys_connection = await get_table_info(
        conn, "setting_drafts_provider_keys_connection"
    )
    thresholds_connection = await get_table_info(
        conn, "setting_drafts_thresholds_connection"
    )

    tables = [
        t
        for t in [
            entry_table,
            agents_connection,
            auth_item_keys_connection,
            auths_connection,
            colors_connection,
            departments_connection,
            descriptions_connection,
            flags_connection,
            items_connection,
            names_connection,
            profiles_connection,
            provider_keys_connection,
            thresholds_connection,
        ]
        if t is not None
    ]

    return DocsResponse(
        name="setting_drafts",
        type="entry",
        description=(
            "Setting draft artifacts with extensive resource connections. "
            "Each draft links to agents, auth item keys, auths, colors, departments, descriptions, "
            "flags, items, names, profiles, provider keys, and thresholds via connection tables. "
            "Reads are served from the setting_drafts_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_setting_draft,
                description=(
                    "Creates a new setting draft, writing to setting_drafts_entry "
                    "and all relevant connection tables."
                ),
            ),
            get_operation_info(
                refresh_setting_drafts,
                description="Refreshes setting_drafts_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_setting_drafts,
                description="Batch retrieves setting drafts by IDs from setting_drafts_mv.",
            ),
            get_operation_info(
                search_setting_drafts,
                description="Filtered paginated search against setting_drafts_mv.",
            ),
        ],
    )
