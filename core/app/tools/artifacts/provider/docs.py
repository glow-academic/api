"""Provider artifact documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.artifacts.provider.create import create_provider
from app.tools.artifacts.provider.delete import delete_providers
from app.tools.artifacts.provider.get import get_providers
from app.tools.artifacts.provider.search import search_providers
from app.tools.artifacts.provider.update import update_provider


async def get_provider_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the provider artifact."""
    artifact_table = await get_table_info(conn, "provider_artifact")
    tables = [t for t in [artifact_table] if t is not None]

    return DocsResponse(
        name="provider",
        type="artifact",
        description=(
            "Providers define AI service provider configurations with API endpoints and keys. "
            "Each provider links to resources (names, descriptions, departments, endpoints, keys, values) "
            "via junction tables."
        ),
        tables=tables,
        operations=[
            get_operation_info(
                create_provider,
                description="Creates a new provider artifact with optional resource links.",
            ),
            get_operation_info(
                update_provider,
                description="Updates an existing provider's resource links.",
            ),
            get_operation_info(
                get_providers,
                description="Batch retrieves providers by IDs with optional junction data.",
            ),
            get_operation_info(
                search_providers,
                description="Filtered paginated search returning matching provider IDs.",
            ),
            get_operation_info(
                delete_providers,
                description="Deletes providers by IDs. Supports soft delete (active=false) or hard delete (cascade).",
            ),
        ],
    )
