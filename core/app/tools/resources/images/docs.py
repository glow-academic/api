"""Images resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.images.create import create_image
from app.tools.resources.images.get import get_images
from app.tools.resources.images.search import search_images


async def get_images_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the images resource."""
    resource_table = await get_table_info(conn, "images_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="images",
        type="resource",
        description="Image references for scenarios and documents.",
        tables=tables,
        operations=[
            get_operation_info(
                create_image,
                description="Creates a new images resource.",
            ),
            get_operation_info(
                get_images,
                description="Batch retrieves images by IDs.",
            ),
            get_operation_info(
                search_images,
                description="Filtered paginated search returning matching images.",
            ),
        ],
    )
