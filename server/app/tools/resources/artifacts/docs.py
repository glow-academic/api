"""Artifacts resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.artifacts.create import create_artifact
from app.tools.resources.artifacts.get import get_artifacts
from app.tools.resources.artifacts.search import search_artifacts


async def get_artifacts_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the artifacts resource."""
    resource_table = await get_table_info(conn, "artifacts_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="artifacts",
        type="resource",
        description="Artifact type references used by tools.",
        tables=tables,
        operations=[
            get_operation_info(
                create_artifact,
                description="Creates a new artifacts resource.",
            ),
            get_operation_info(
                get_artifacts,
                description="Batch retrieves artifacts by IDs.",
            ),
            get_operation_info(
                search_artifacts,
                description="Filtered paginated search returning matching artifacts.",
            ),
        ],
    )
