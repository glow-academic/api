"""Tokens GET — batch get from tokens_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.tokens.types import GetTokenResponse

MV_NAME = "tokens_mv"


async def get_tokens(
    conn: asyncpg.Connection,
    ids: list[UUID],
    bypass_mv: bool = False,
) -> list[GetTokenResponse]:
    """Get tokens by IDs from tokens_mv."""
    if not ids:
        return []

    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, created_at, generated, mcp, active, run_id,
               input_tokens, output_tokens, cached_input_tokens, session_id
        FROM {source}
        WHERE id = ANY($1)
        """,
        ids,
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
