"""Field title — thin wrapper over shared title_group_impl.

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

ARTIFACT_TYPE = "field"


class TitleFieldApiRequest(TitleGroupRequest):
    """Request body for POST /field/title."""


class TitleFieldApiResponse(TitleGroupResponse):
    """Response body for POST /field/title."""


async def title_field_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    **kwargs,
) -> TitleFieldApiResponse:
    """Rename a field group; see title_group_impl for full semantics."""
    result = await title_group_impl(
        pool, redis, artifact_type=ARTIFACT_TYPE, **kwargs,
    )
    return TitleFieldApiResponse.model_validate(result.model_dump())
