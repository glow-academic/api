"""Tokens search — filtered/paginated query against tokens_mv."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.tokens.types import GetTokenResponse

MV_NAME = "tokens_mv"


async def search_tokens(
    conn: asyncpg.Connection,
    run_ids: list[UUID] | None = None,
    session_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    mcp: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetTokenResponse]:
    """Search tokens from tokens_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, created_at, generated, mcp, active, run_id,
               input_tokens, output_tokens, cached_input_tokens, session_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR run_id = ANY($1))
          AND ($2::uuid[] IS NULL OR session_id = ANY($2))
          AND ($3::timestamptz IS NULL OR created_at >= $3)
          AND ($4::timestamptz IS NULL OR created_at <= $4)
          AND ($5::boolean IS NULL OR mcp = $5)
        ORDER BY created_at DESC
        LIMIT $6 OFFSET $7
        """,
        run_ids,
        session_ids,
        date_from,
        date_to,
        mcp,
        limit,
        offset,
    )

    return [
        GetTokenResponse(
            id=r["id"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
            active=r["active"],
            run_id=r["run_id"],
            input_tokens=r["input_tokens"],
            output_tokens=r["output_tokens"],
            cached_input_tokens=r["cached_input_tokens"],
            session_id=r["session_id"],
        )
        for r in rows
    ]
