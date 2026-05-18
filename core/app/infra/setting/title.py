"""Setting title — thin wrapper over shared title_group_impl.

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

ARTIFACT_TYPE = "setting"


class TitleSettingApiRequest(TitleGroupRequest):
    """Request body for POST /setting/title."""


class TitleSettingApiResponse(TitleGroupResponse):
    """Response body for POST /setting/title."""


async def title_setting_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    **kwargs,
) -> TitleSettingApiResponse:
    """Rename a setting group; see title_group_impl for full semantics."""
    result = await title_group_impl(
        pool, redis, artifact_type=ARTIFACT_TYPE, **kwargs,
    )
    return TitleSettingApiResponse.model_validate(result.model_dump())
