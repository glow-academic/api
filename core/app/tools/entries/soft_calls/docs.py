"""Soft calls entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.entries.soft_calls.search import search_soft_calls


async def get_soft_calls_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the soft_calls entry."""
    mv_info = await get_mv_info(conn, "soft_calls_mv")
    entry_table = await get_table_info(conn, "soft_calls_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="soft_calls",
        type="entry",
        description=(
            "Soft calls ledger — append-only record of pending / accepted /"
            " rejected status per LLM-driven soft tool call. Each row is a"
            " state change; ``soft_calls_mv`` collapses to the latest row"
            " per ``call_id``. Vocabulary mirrors permissions_resource:"
            " ``(artifact, operation)``. Used as the canonical lookup for"
            " ack short-circuits and search-time filtering of dormant rows."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_soft_call,
                description="Append a soft-call ledger row (pending / accepted / rejected).",
            ),
            get_operation_info(
                refresh_soft_calls,
                description="Refresh soft_calls_mv concurrently.",
            ),
            get_operation_info(
                get_soft_call,
                description="Latest status for a call_id (optionally constrained by artifact).",
            ),
            get_operation_info(
                search_soft_calls,
                description="Filtered/paginated search against soft_calls_mv.",
            ),
        ],
    )
