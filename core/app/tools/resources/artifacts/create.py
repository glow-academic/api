"""Artifacts CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.artifacts.get import get_artifacts
from app.tools.resources.artifacts.types import GetArtifactResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_artifact(
    conn: asyncpg.Connection,
    artifact: str,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetArtifactResponse:
    """Create an artifact resource (insert or get existing)."""
    artifact_id = await conn.fetchval(
        """
        INSERT INTO artifacts_resource (id, artifact, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, $3)
        ON CONFLICT (artifact) DO UPDATE SET artifact = EXCLUDED.artifact
        RETURNING id
    """,
        artifact,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "artifacts"], redis=redis)
    items = await get_artifacts(conn, [artifact_id], redis, bypass_cache=True)
    return items[0]
