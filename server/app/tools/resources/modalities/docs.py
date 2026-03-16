"""Modalities resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.modalities.create import create_modality
from app.tools.resources.modalities.get import get_modalities
from app.tools.resources.modalities.search import search_modalities


async def get_modalities_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the modalities resource."""
    resource_table = await get_table_info(conn, "modalities_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="modalities",
        type="resource",
        description="Model capability modalities (text, vision, audio).",
        tables=tables,
        operations=[
            get_operation_info(
                create_modality,
                description="Creates a new modalities resource.",
            ),
            get_operation_info(
                get_modalities,
                description="Batch retrieves modalities by IDs.",
            ),
            get_operation_info(
                search_modalities,
                description="Filtered paginated search returning matching modalities.",
            ),
        ],
    )
