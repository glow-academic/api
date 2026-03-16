"""Files entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.files.create import create_file
from app.tools.entries.files.get import get_file
from app.tools.entries.files.search import search_files


async def get_files_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the files entry."""
    entry_table = await get_table_info(conn, "files_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="files",
        type="entry",
        description=(
            "File entries track uploaded or generated files within sessions. "
            "Each file is associated with a session and tracks metadata about generation and status. "
            "Reads are served directly from the files_entry table."
        ),
        materialized_view=None,
        tables=tables,
        operations=[
            get_operation_info(
                create_file,
                description="Creates a new file entry in files_entry table.",
            ),
            get_operation_info(
                get_file,
                description="Retrieves a single file entry by ID from files_entry.",
            ),
            get_operation_info(
                search_files,
                description="Filtered paginated search against files_mv with optional file and mime_type filters.",
            ),
        ],
    )
