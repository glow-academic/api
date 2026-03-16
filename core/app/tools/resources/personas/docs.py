"""Personas resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.personas.create import create_persona
from app.tools.resources.personas.get import get_personas
from app.tools.resources.personas.search import search_personas


async def get_personas_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the personas resource."""
    resource_table = await get_table_info(conn, "personas_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="personas",
        type="resource",
        description="Persona reference IDs linking to persona artifacts.",
        tables=tables,
        operations=[
            get_operation_info(
                create_persona,
                description="Creates a new personas resource.",
            ),
            get_operation_info(
                get_personas,
                description="Batch retrieves personas by IDs.",
            ),
            get_operation_info(
                search_personas,
                description="Filtered paginated search returning matching personas.",
            ),
        ],
    )
