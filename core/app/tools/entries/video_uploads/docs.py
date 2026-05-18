"""Video uploads entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.video_uploads.create import create_video_upload
from app.tools.entries.video_uploads.get import get_video_upload
from app.tools.entries.video_uploads.refresh import refresh_video_uploads
from app.tools.entries.video_uploads.search import search_video_uploads


async def get_video_uploads_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the video_uploads entry."""
    mv_info = await get_mv_info(conn, "video_uploads_mv")
    entry_table = await get_table_info(conn, "video_uploads_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="video_uploads",
        type="entry",
        description=(
            "Video upload entries link video artifacts to upload artifacts via a session. "
            "Each row associates a video with an upload, recording when and how it was generated. "
            "Reads are served from the video_uploads_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_video_upload,
                description=(
                    "Creates a new video_uploads entry linking a video to an upload "
                    "within a session."
                ),
            ),
            get_operation_info(
                refresh_video_uploads,
                description="Refreshes video_uploads_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_video_upload,
                description="Batch retrieves video_uploads entries by ID from video_uploads_mv.",
            ),
            get_operation_info(
                search_video_uploads,
                description="Filtered paginated search against video_uploads_mv.",
            ),
        ],
    )
