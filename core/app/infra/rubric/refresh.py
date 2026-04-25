"""Rubric refresh — debounced via MVRefresher (uses shared enqueue helper)."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.refresh.queue import enqueue_refreshes
from app.infra.refresh.types import RefreshResponse

ARTIFACT_TYPE = "rubric"

ALL_TARGETS = [
    "rubric_drafts_mv",
    "runs_mv",
    "messages_mv",
    "calls_mv",
    "groups_mv",
    "group_names_mv",
]

_TAGS = ["rubrics", "artifacts"]


class RefreshRubricApiRequest(BaseModel):
    """Request model for rubric refresh endpoint."""

    targets: list[str] | None = Field(
        None,
        description="MV targets to refresh (omit for all). Options: rubric_drafts_mv",
    )
    idempotency_key: UUID | None = Field(None, description="Operation key for ack")
    accept: bool = Field(
        True,
        description="Accept or reject. Only meaningful with idempotency_key",
    )


async def refresh_rubric_impl(
    pool: asyncpg.Pool,
    redis: Redis | None,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    request: RefreshRubricApiRequest | None = None,
    targets: list[str] | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    operation_key: UUID | None = None,
    **_kwargs,
) -> RefreshResponse:
    """Rubric refresh — permission-check + enqueue, no synchronous MV refresh."""
    if request is not None:
        targets = targets or request.targets
        idempotency_key = idempotency_key or request.idempotency_key
        if idempotency_key and accept is None:
            accept = request.accept

    effective_targets = targets or ALL_TARGETS
    effective_op_key = operation_key or idempotency_key

    return await enqueue_refreshes(
        pool, redis,
        profile_id=profile_id,
        session_id=session_id,
        artifact_type=ARTIFACT_TYPE,
        targets=effective_targets,
        idempotency_key=effective_op_key,
        tags=_TAGS,
        soft=soft,
        accept=accept,
    )
