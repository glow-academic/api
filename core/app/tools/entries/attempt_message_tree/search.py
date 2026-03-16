"""Attempt message tree search — filtered/paginated query against attempt_message_tree_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_message_tree.types import (
    GetAttemptMessageTreeResponse,
)

MV_NAME = "attempt_message_tree_mv"


async def search_attempt_message_trees(
    conn: asyncpg.Connection,
    message_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetAttemptMessageTreeResponse]:
    """Search attempt_message_tree entries from attempt_message_tree_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT message_id, branch_path, depth
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR message_id = ANY($1))
        ORDER BY depth DESC
        LIMIT $2 OFFSET $3
        """,
        message_ids,
        limit,
        offset,
    )

    return [GetAttemptMessageTreeResponse(**dict(r)) for r in rows]
