"""Tokens CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.tokens.types import CreateTokenResponse


async def create_token(
    conn: asyncpg.Connection,
    run_id: UUID,
    session_id: UUID,
    *,
    id: UUID | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached_input_tokens: int = 0,
    mcp: bool = False,
    soft: bool = False,
) -> CreateTokenResponse:
    """Create a tokens entry."""
    token_id = await conn.fetchval(
        """
        INSERT INTO tokens_entry (id, run_id, input_tokens, output_tokens, cached_input_tokens, session_id, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        RETURNING id
        """,
        run_id,
        input_tokens,
        output_tokens,
        cached_input_tokens,
        session_id,
        not soft,
        mcp,
        id,
    )

    if token_id is None:
        raise ValueError("Failed to create tokens entry")

    return CreateTokenResponse(id=token_id)
