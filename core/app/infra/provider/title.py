"""Provider title — thin wrapper over shared title_group_impl.

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

ARTIFACT_TYPE = "provider"


class TitleProviderApiRequest(TitleGroupRequest):
    """Request body for POST /provider/title."""


class TitleProviderApiResponse(TitleGroupResponse):
    """Response body for POST /provider/title."""


async def title_provider_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    **kwargs,
) -> TitleProviderApiResponse:
    """Rename a provider group; see title_group_impl for full semantics."""
    result = await title_group_impl(
        pool, redis, artifact_type=ARTIFACT_TYPE, **kwargs,
    )
    return TitleProviderApiResponse.model_validate(result.model_dump())
