"""Profile group — thin wrapper over shared resolve_group_impl.

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

ARTIFACT_TYPE = "profile"


class GroupProfileApiRequest(GroupResolveRequest):
    """Request body for POST /profile/group."""


class GroupProfileApiResponse(GroupResolveResponse):
    """Response body for POST /profile/group."""


async def group_profile_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    **kwargs,
) -> GroupProfileApiResponse:
    """Resolve/create an profile group; see resolve_group_impl for full semantics."""
    result = await resolve_group_impl(
        pool, redis, artifact_type=ARTIFACT_TYPE, **kwargs,
    )
    return GroupProfileApiResponse.model_validate(result.model_dump())
