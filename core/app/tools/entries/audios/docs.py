"""Audios entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.audios.create import create_audio
from app.tools.entries.audios.refresh import refresh_audios_internal
from app.tools.entries.audios.search import search_audios


async def get_audios_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the audios entry."""
    mv_info = await get_mv_info(conn, "audios_mv")
    entry_table = await get_table_info(conn, "audios_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="audios",
        type="entry",
        description=(
            "Audio entries track generated or uploaded audio assets. "
            "Each audio is associated with a session and stores metadata about length and generation status. "
            "Reads are served from the audios_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_audio,
                description="Creates a new audio entry in audios_entry table.",
            ),
            get_operation_info(
                refresh_audios_internal,
                description="Refreshes audios_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                search_audios,
                description="Filtered paginated search against audios_mv with optional file and voice filters.",
            ),
        ],
    )
