"""Attempt title — thin wrapper over shared title_group_impl.

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

ARTIFACT_TYPE = "attempt"


class TitleAttemptApiRequest(TitleGroupRequest):
    """Request body for POST /attempt/title."""


class TitleAttemptApiResponse(TitleGroupResponse):
    """Response body for POST /attempt/title."""


async def title_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    **kwargs,
) -> TitleAttemptApiResponse:
    """Rename a attempt group; see title_group_impl for full semantics."""
    result = await title_group_impl(
        pool, redis, artifact_type=ARTIFACT_TYPE, **kwargs,
    )
    return TitleAttemptApiResponse.model_validate(result.model_dump())
