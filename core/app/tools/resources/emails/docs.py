"""Emails resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.emails.create import create_email
from app.tools.resources.emails.get import get_emails
from app.tools.resources.emails.search import search_emails


async def get_emails_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the emails resource."""
    resource_table = await get_table_info(conn, "emails_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="emails",
        type="resource",
        description="Email addresses associated with profiles.",
        tables=tables,
        operations=[
            get_operation_info(
                create_email,
                description="Creates a new emails resource.",
            ),
            get_operation_info(
                get_emails,
                description="Batch retrieves emails by IDs.",
            ),
            get_operation_info(
                search_emails,
                description="Filtered paginated search returning matching emails.",
            ),
        ],
    )
