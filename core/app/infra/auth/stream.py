"""Canonical per-artifact stream impl — auth."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis

from app.infra.auth.group import group_auth_impl
from app.infra.stream.sse import build_artifact_stream_impl


async def stream_auth_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    group_id: UUID | None = None,
    run_id: UUID | None = None,
) -> StreamingResponse:
    if group_id is None:
        group_result = await group_auth_impl(
            pool, redis,
            profile_id=profile_id,
            session_id=session_id,
        )
        group_id = group_result.group_id
    return await build_artifact_stream_impl(
        group_id=group_id,
        run_id=run_id,
        artifact="auth",
    )
