"""Settings resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.settings.create import create_setting
from app.tools.resources.settings.get import get_settings
from app.tools.resources.settings.search import search_settings


async def get_settings_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the settings resource."""
    resource_table = await get_table_info(conn, "settings_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="settings",
        type="resource",
        description="Setting reference IDs linking to setting artifacts.",
        tables=tables,
        operations=[
            get_operation_info(
                create_setting,
                description="Creates a new settings resource.",
            ),
            get_operation_info(
                get_settings,
                description="Batch retrieves settings by IDs.",
            ),
            get_operation_info(
                search_settings,
                description="Filtered paginated search returning matching settings.",
            ),
        ],
    )
