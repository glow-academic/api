"""Voices resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.voices.create import create_voice
from app.tools.resources.voices.get import get_voices
from app.tools.resources.voices.search import search_voices


async def get_voices_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the voices resource."""
    resource_table = await get_table_info(conn, "voices_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="voices",
        type="resource",
        description="Voice configuration identifiers for agents and personas.",
        tables=tables,
        operations=[
            get_operation_info(
                create_voice,
                description="Creates a new voices resource.",
            ),
            get_operation_info(
                get_voices,
                description="Batch retrieves voices by IDs.",
            ),
            get_operation_info(
                search_voices,
                description="Filtered paginated search returning matching voices.",
            ),
        ],
    )
