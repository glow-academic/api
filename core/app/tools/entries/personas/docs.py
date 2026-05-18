"""Personas entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.personas.create import create_personas
from app.tools.entries.personas.get import get_personas


async def get_personas_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the personas entry."""
    entry_table = await get_table_info(conn, "personas_entry")
    personas_connection = await get_table_info(conn, "personas_personas_connection")

    tables = [t for t in [entry_table, personas_connection] if t is not None]

    return DocsResponse(
        name="personas",
        type="entry",
        description=(
            "Personas entries act as collection containers for persona resources. "
            "Each personas entry can link to multiple persona resources via the personas_personas_connection table. "
            "Reads are served directly from the personas_entry table with joined connection data."
        ),
        materialized_view=None,
        tables=tables,
        operations=[
            get_operation_info(
                create_personas,
                description="Creates a new personas entry with optional connections to persona resources.",
            ),
            get_operation_info(
                get_personas,
                description="Batch retrieves personas entries by IDs from personas_entry with all persona connections.",
            ),
        ],
    )
