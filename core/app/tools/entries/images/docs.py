"""Images entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.images.create import create_image
from app.tools.entries.images.get import get_image
from app.tools.entries.images.search import search_images


async def get_images_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the images entry."""
    entry_table = await get_table_info(conn, "images_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="images",
        type="entry",
        description=(
            "Image entries track generated or uploaded image assets. "
            "Each image is associated with a session and stores metadata about generation and status. "
            "Reads are served directly from the images_entry table."
        ),
        materialized_view=None,
        tables=tables,
        operations=[
            get_operation_info(
                create_image,
                description="Creates a new image entry in images_entry table.",
            ),
            get_operation_info(
                get_image,
                description="Retrieves a single image entry by ID from images_entry.",
            ),
            get_operation_info(
                search_images,
                description="Filtered paginated search against images_mv with optional file and quality filters.",
            ),
        ],
    )
