"""Audios resource CREATE — reusable data-access layer.

Mirror of ``tools/resources/images/create.py``. Creates a row in the
``audios_resource`` canonical library. Called by
``audio_upload_attempt_impl`` whenever a captured or uploaded audio needs
to be promoted to a publicly referenceable asset.
"""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.audios.types import GetAudioResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_audio_resource(
    conn: asyncpg.Connection,
    name: str,
    description: str,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetAudioResponse:
    """Create an audios_resource row and return it."""
    row = await conn.fetchrow(
        """
        INSERT INTO audios_resource (id, name, description, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, $4)
        RETURNING id, name, description, created_at, active, generated, mcp
        """,
        name,
        description,
        not soft,
        mcp,
        id,
    )
    if row is None:
        raise ValueError("Failed to create audios_resource")

    await invalidate_tags(["resources", "audios"], redis=redis)

    return GetAudioResponse(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        created_at=row["created_at"],
        active=row["active"],
        generated=row["generated"],
        mcp=row["mcp"],
    )
