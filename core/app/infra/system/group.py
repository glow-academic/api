"""System group — thin wrapper over shared resolve_group_impl.

Canonical logic lives in app.infra.group.resolve. This module only declares
the artifact type and per-artifact request/response subclasses so OpenAPI
schemas remain named per artifact.
"""

from __future__ import annotations

import asyncpg
from redis.asyncio import Redis

from app.infra.group.resolve import (
    GroupResolveRequest,
    GroupResolveResponse,
    resolve_group_impl,
)

ARTIFACT_TYPE = "system"


class GroupSystemApiRequest(GroupResolveRequest):
    """Request body for POST /system/group."""


class GroupSystemApiResponse(GroupResolveResponse):
    """Response body for POST /system/group."""


async def group_system_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    **kwargs,
) -> GroupSystemApiResponse:
    """Resolve/create an system group; see resolve_group_impl for full semantics."""
    result = await resolve_group_impl(
        pool, redis, artifact_type=ARTIFACT_TYPE, **kwargs,
    )
    return GroupSystemApiResponse.model_validate(result.model_dump())
