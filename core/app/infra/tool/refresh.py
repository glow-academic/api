"""Tool refresh logic — composable infra architecture."""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.refresh.types import RefreshResponse
from app.tools.entries.calls.refresh import refresh_calls_internal
from app.tools.entries.group_names.refresh import refresh_group_names
from app.tools.entries.groups.refresh import refresh_groups
from app.tools.entries.messages.refresh import refresh_messages_internal
from app.tools.entries.refreshes.create import create_refresh
from app.tools.entries.runs.refresh import refresh_runs_internal
from app.tools.entries.tool_drafts.refresh import refresh_tool_drafts

ALL_TARGETS = [
    "tool_drafts_mv",
    "runs_mv",
    "messages_mv",
    "calls_mv",
    "groups_mv",
    "group_names_mv",
]

_REFRESH_FNS = {
    "tool_drafts_mv": refresh_tool_drafts,
    "runs_mv": refresh_runs_internal,
    "messages_mv": refresh_messages_internal,
    "calls_mv": refresh_calls_internal,
    "groups_mv": refresh_groups,
    "group_names_mv": refresh_group_names,
}

_TAGS = ["tools", "artifacts"]


class RefreshToolApiRequest(BaseModel):
    """Request model for tool refresh endpoint."""

    targets: list[str] | None = Field(
        None,
        description="MV targets to refresh (omit for all). Options: tool_drafts_mv",
    )
    idempotency_key: UUID | None = Field(None, description="Operation key for ack")
    accept: bool = Field(
        True,
        description="Accept or reject. Only meaningful with idempotency_key",
    )


async def refresh_tool_impl(
    pool: asyncpg.Pool,
    redis: Redis | None,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    request: RefreshToolApiRequest | None = None,
    targets: list[str] | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    operation_key: UUID | None = None,
    **_kwargs,
) -> RefreshResponse:
    """Refresh tool materialized views and invalidate caches."""
    if request is not None:
        targets = targets or request.targets
        idempotency_key = idempotency_key or request.idempotency_key
        if idempotency_key and accept is None:
            accept = request.accept

    effective_targets = targets or ALL_TARGETS
    effective_operation_key = operation_key or idempotency_key

    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    if accept is not None and idempotency_key is not None:
        if accept:
            await _execute_refreshes(pool, effective_targets)
            if session_id and effective_operation_key:
                async with pool.acquire() as conn:
                    for target in effective_targets:
                        await create_refresh(
                            conn,
                            operation_key=effective_operation_key,
                            artifact_type="tool",
                            target=target,
                            session_id=session_id,
                        )
            if redis is not None:
                from app.utils.cache.invalidate_tags import invalidate_tags

                await invalidate_tags(_TAGS, redis=redis)
        return RefreshResponse(
            success=True,
            refreshed_views=effective_targets if accept else [],
            invalidated_tags=_TAGS if accept else [],
            idempotency_key=effective_operation_key,
        )

    if soft:
        if session_id and effective_operation_key:
            async with pool.acquire() as conn:
                for target in effective_targets:
                    await create_refresh(
                        conn,
                        operation_key=effective_operation_key,
                        artifact_type="tool",
                        target=target,
                        session_id=session_id,
                    )
        return RefreshResponse(
            success=True,
            refreshed_views=[],
            invalidated_tags=[],
            idempotency_key=effective_operation_key,
        )

    await _execute_refreshes(pool, effective_targets)

    if session_id and effective_operation_key:
        async with pool.acquire() as conn:
            for target in effective_targets:
                await create_refresh(
                    conn,
                    operation_key=effective_operation_key,
                    artifact_type="tool",
                    target=target,
                    session_id=session_id,
                )

    if redis is not None:
        from app.utils.cache.invalidate_tags import invalidate_tags

        await invalidate_tags(_TAGS, redis=redis)

    return RefreshResponse(
        success=True,
        refreshed_views=effective_targets,
        invalidated_tags=_TAGS,
        idempotency_key=effective_operation_key,
    )


async def _execute_refreshes(pool: asyncpg.Pool, targets: list[str]) -> None:
    """Execute MV refreshes in parallel for the given targets."""

    async def _refresh(target: str) -> None:
        fn = _REFRESH_FNS.get(target)
        if fn:
            async with pool.acquire() as conn:
                await fn(conn)

    await asyncio.gather(*[_refresh(target) for target in targets])
