"""Agent title — thin wrapper over shared title_group_impl.

Canonical logic lives in app.infra.group.title. This module only declares
the artifact type and per-artifact request/response subclasses so OpenAPI
schemas remain named per artifact.
"""

from __future__ import annotations

import asyncpg
from redis.asyncio import Redis

from app.infra.group.title import (
    TitleGroupRequest,
    TitleGroupResponse,
    title_group_impl,
)

ARTIFACT_TYPE = "agent"


class TitleAgentApiRequest(TitleGroupRequest):
    """Request body for POST /agent/title."""


class TitleAgentApiResponse(TitleGroupResponse):
    """Response body for POST /agent/title."""


async def title_agent_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    **kwargs,
) -> TitleAgentApiResponse:
    """Rename a agent group; see title_group_impl for full semantics."""
    result = await title_group_impl(
        pool, redis, artifact_type=ARTIFACT_TYPE, **kwargs,
    )
    return TitleAgentApiResponse.model_validate(result.model_dump())
