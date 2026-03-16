"""Documents resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.documents.create import create_document
from app.tools.resources.documents.get import get_documents
from app.tools.resources.documents.search import search_documents


async def get_documents_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the documents resource."""
    resource_table = await get_table_info(conn, "documents_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="documents",
        type="resource",
        description="Document reference IDs linking to document artifacts.",
        tables=tables,
        operations=[
            get_operation_info(
                create_document,
                description="Creates a new documents resource.",
            ),
            get_operation_info(
                get_documents,
                description="Batch retrieves documents by IDs.",
            ),
            get_operation_info(
                search_documents,
                description="Filtered paginated search returning matching documents.",
            ),
        ],
    )
