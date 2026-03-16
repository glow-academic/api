"""Videos resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.videos.create import create_video
from app.tools.resources.videos.get import get_videos
from app.tools.resources.videos.search import search_videos


async def get_videos_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the videos resource."""
    resource_table = await get_table_info(conn, "videos_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="videos",
        type="resource",
        description="Video references for scenario content.",
        tables=tables,
        operations=[
            get_operation_info(
                create_video,
                description="Creates a new videos resource.",
            ),
            get_operation_info(
                get_videos,
                description="Batch retrieves videos by IDs.",
            ),
            get_operation_info(
                search_videos,
                description="Filtered paginated search returning matching videos.",
            ),
        ],
    )
