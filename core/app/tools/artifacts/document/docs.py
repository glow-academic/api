"""Document artifact documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.artifacts.document.create import create_document
from app.tools.artifacts.document.delete import delete_documents
from app.tools.artifacts.document.get import get_documents
from app.tools.artifacts.document.search import search_documents
from app.tools.artifacts.document.update import update_document


async def get_document_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the document artifact."""
    artifact_table = await get_table_info(conn, "document_artifact")
    tables = [t for t in [artifact_table] if t is not None]

    return DocsResponse(
        name="document",
        type="artifact",
        description=(
            "Documents store reference materials and files for scenarios. "
            "Each document links to resources (names, descriptions, departments, "
            "files, images, parameter_fields, texts) via junction tables."
        ),
        tables=tables,
        operations=[
            get_operation_info(
                create_document,
                description="Creates a new document artifact with optional resource links.",
            ),
            get_operation_info(
                update_document,
                description="Updates an existing document's resource links.",
            ),
            get_operation_info(
                get_documents,
                description="Batch retrieves documents by IDs with optional junction data.",
            ),
            get_operation_info(
                search_documents,
                description="Filtered paginated search returning matching document IDs.",
            ),
            get_operation_info(
                delete_documents,
                description="Deletes documents by IDs. Supports soft delete (active=false) or hard delete (cascade).",
            ),
        ],
    )
