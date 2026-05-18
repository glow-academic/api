"""Tokens entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.tokens.create import create_token
from app.tools.entries.tokens.get import get_tokens
from app.tools.entries.tokens.refresh import refresh_tokens
from app.tools.entries.tokens.search import search_tokens


async def get_tokens_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the tokens entry."""
    mv_info = await get_mv_info(conn, "tokens_mv")
    entry_table = await get_table_info(conn, "tokens_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="tokens",
        type="entry",
        description=(
            "Token entries record LLM token usage per run. "
            "Each entry belongs to a run and tracks input, output, and cached input tokens. "
            "Reads are served from the tokens_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_token,
                description="Creates a new tokens entry for a run.",
            ),
            get_operation_info(
                refresh_tokens,
                description="Refreshes tokens_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_tokens,
                description="Batch retrieves token entries by IDs from tokens_mv.",
            ),
            get_operation_info(
                search_tokens,
                description="Filtered paginated search against tokens_mv.",
            ),
        ],
    )
