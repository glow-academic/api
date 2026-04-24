"""Canonical per-artifact stream impl — field."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis

from app.infra.field.group import group_field_impl
from app.infra.stream.sse import build_artifact_stream_impl


async def stream_field_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    group_id: UUID | None = None,
) -> StreamingResponse:
    if group_id is None:
        group_result = await group_field_impl(
            pool, redis,
            profile_id=profile_id,
            session_id=session_id,
        )
        group_id = group_result.group_id
    return await build_artifact_stream_impl(
        group_id=group_id,
        artifact="field",
    )
