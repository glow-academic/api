"""Emails CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.emails.get import get_emails
from app.tools.resources.emails.types import GetEmailResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_email(
    conn: asyncpg.Connection,
    email: str,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetEmailResponse:
    """Create an email resource (insert or get existing)."""
    email_id = await conn.fetchval(
        """
        INSERT INTO emails_resource (id, email, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, $3)
        ON CONFLICT (email) DO UPDATE SET email = EXCLUDED.email
        RETURNING id
    """,
        email,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "emails"], redis=redis)
    items = await get_emails(conn, [email_id], redis, bypass_cache=True)
    return items[0]
