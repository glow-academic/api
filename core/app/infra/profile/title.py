"""Profile title — thin wrapper over shared title_group_impl.

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

ARTIFACT_TYPE = "profile"


class TitleProfileApiRequest(TitleGroupRequest):
    """Request body for POST /profile/title."""


class TitleProfileApiResponse(TitleGroupResponse):
    """Response body for POST /profile/title."""


async def title_profile_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    **kwargs,
) -> TitleProfileApiResponse:
    """Rename a profile group; see title_group_impl for full semantics."""
    result = await title_group_impl(
        pool, redis, artifact_type=ARTIFACT_TYPE, **kwargs,
    )
    return TitleProfileApiResponse.model_validate(result.model_dump())
