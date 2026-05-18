"""Test invocation completion search — filtered/paginated query against test_invocation_completion_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.test_invocation_completion.types import (
    GetTestInvocationCompletionResponse,
)

MV_NAME = "test_invocation_completion_mv"


async def search_test_invocation_completions(
    conn: asyncpg.Connection,
    invocation_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetTestInvocationCompletionResponse]:
    """Search test_invocation_completion entries from test_invocation_completion_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, created_at, generated, mcp, active, invocation_id, stop, error, message, call_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR invocation_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        invocation_ids,
        limit,
        offset,
    )

    return [GetTestInvocationCompletionResponse(**dict(r)) for r in rows]
