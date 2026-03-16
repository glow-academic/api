"""Profile drafts entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.profile_drafts.create import create_profile_draft
from app.tools.entries.profile_drafts.get import get_profile_drafts
from app.tools.entries.profile_drafts.refresh import refresh_profile_drafts
from app.tools.entries.profile_drafts.search import search_profile_drafts


async def get_profile_drafts_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the profile_drafts entry."""
    mv_info = await get_mv_info(conn, "profile_drafts_mv")
    entry_table = await get_table_info(conn, "profile_drafts_entry")
    departments_connection = await get_table_info(
        conn, "profile_drafts_departments_connection"
    )
    profiles_connection = await get_table_info(
        conn, "profile_drafts_profiles_connection"
    )
    emails_connection = await get_table_info(conn, "profile_drafts_emails_connection")
    flags_connection = await get_table_info(conn, "profile_drafts_flags_connection")
    names_connection = await get_table_info(conn, "profile_drafts_names_connection")
    request_limits_connection = await get_table_info(
        conn, "profile_drafts_request_limits_connection"
    )
    roles_connection = await get_table_info(conn, "profile_drafts_roles_connection")

    tables = [
        t
        for t in [
            entry_table,
            profiles_connection,
            departments_connection,
            emails_connection,
            flags_connection,
            names_connection,
            request_limits_connection,
            roles_connection,
        ]
        if t is not None
    ]

    return DocsResponse(
        name="profile_drafts",
        type="entry",
        description=(
            "Profile draft artifacts with support for multiple resource connections. "
            "Each draft links to owner profiles, departments, emails, flags, names, request limits, and roles "
            "via connection tables. "
            "Reads are served from the profile_drafts_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_profile_draft,
                description=(
                    "Creates a new profile draft, writing to profile_drafts_entry "
                    "and all relevant connection tables."
                ),
            ),
            get_operation_info(
                refresh_profile_drafts,
                description="Refreshes profile_drafts_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_profile_drafts,
                description="Batch retrieves profile drafts by IDs from profile_drafts_mv.",
            ),
            get_operation_info(
                search_profile_drafts,
                description="Filtered paginated search against profile_drafts_mv.",
            ),
        ],
    )
