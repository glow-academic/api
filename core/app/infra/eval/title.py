"""Eval title — thin wrapper over shared title_group_impl.

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

ARTIFACT_TYPE = "eval"


class TitleEvalApiRequest(TitleGroupRequest):
    """Request body for POST /eval/title."""


class TitleEvalApiResponse(TitleGroupResponse):
    """Response body for POST /eval/title."""


async def title_eval_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    **kwargs,
) -> TitleEvalApiResponse:
    """Rename a eval group; see title_group_impl for full semantics."""
    result = await title_group_impl(
        pool, redis, artifact_type=ARTIFACT_TYPE, **kwargs,
    )
    return TitleEvalApiResponse.model_validate(result.model_dump())
