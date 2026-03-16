"""Files resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.files.create import create_file
from app.tools.resources.files.get import get_files
from app.tools.resources.files.search import search_files


async def get_files_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the files resource."""
    resource_table = await get_table_info(conn, "files_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="files",
        type="resource",
        description="File attachment records for document resources.",
        tables=tables,
        operations=[
            get_operation_info(
                create_file,
                description="Creates a new files resource.",
            ),
            get_operation_info(
                get_files,
                description="Batch retrieves files by IDs.",
            ),
            get_operation_info(
                search_files,
                description="Filtered paginated search returning matching files.",
            ),
        ],
    )
