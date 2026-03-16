"""Profile Personas CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.profile_personas.get import get_profile_personas
from app.tools.resources.profile_personas.types import (
    GetProfilePersonaResponse,
)
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_profile_persona(
    conn: asyncpg.Connection,
    profile_id: UUID,
    persona_id: UUID,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetProfilePersonaResponse:
    """Create a profile_persona resource (ON CONFLICT on (persona_id, profile_id))."""
    row_id = await conn.fetchval(
        """
        INSERT INTO profile_personas_resource (id, profile_id, persona_id, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, $4)
        ON CONFLICT (persona_id, profile_id) DO UPDATE SET persona_id = EXCLUDED.persona_id
        RETURNING id
        """,
        profile_id,
        persona_id,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "profile_personas"], redis=redis)
    items = await get_profile_personas(conn, [row_id], redis, bypass_cache=True)
    return items[0]
