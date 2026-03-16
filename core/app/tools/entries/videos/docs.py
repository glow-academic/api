"""Videos entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.videos.create import create_video
from app.tools.entries.videos.get import get_video
from app.tools.entries.videos.refresh import refresh_videos_internal
from app.tools.entries.videos.search import search_videos


async def get_videos_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the videos entry."""
    mv_info = await get_mv_info(conn, "videos_mv")
    entry_table = await get_table_info(conn, "videos_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="videos",
        type="entry",
        description=(
            "Videos entries represent video content stored or generated during sessions. "
            "Each videos entry tracks a video associated with a session and its length in seconds. "
            "Reads are served from the videos_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_video,
                description="Creates a new videos entry with optional length specification.",
            ),
            get_operation_info(
                refresh_videos_internal,
                description="Refreshes videos_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_video,
                description="Batch retrieves videos entries by IDs from videos_mv.",
            ),
            get_operation_info(
                search_videos,
                description="Filtered paginated search against videos_mv.",
            ),
        ],
    )
