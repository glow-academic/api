"""Image uploads entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.image_uploads.create import create_image_upload
from app.tools.entries.image_uploads.get import get_image_upload
from app.tools.entries.image_uploads.refresh import refresh_image_uploads
from app.tools.entries.image_uploads.search import search_image_uploads


async def get_image_uploads_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the image_uploads entry."""
    mv_info = await get_mv_info(conn, "image_uploads_mv")
    entry_table = await get_table_info(conn, "image_uploads_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="image_uploads",
        type="entry",
        description=(
            "Image upload entries link image artifacts to upload artifacts via a session. "
            "Each row associates an image with an upload, recording when and how it was generated. "
            "Reads are served from the image_uploads_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_image_upload,
                description=(
                    "Creates a new image_uploads entry linking an image to an upload "
                    "within a session."
                ),
            ),
            get_operation_info(
                refresh_image_uploads,
                description="Refreshes image_uploads_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_image_upload,
                description="Batch retrieves image_uploads entries by ID from image_uploads_mv.",
            ),
            get_operation_info(
                search_image_uploads,
                description="Filtered paginated search against image_uploads_mv.",
            ),
        ],
    )
