"""Scenario refresh logic — composable infra architecture.

Composes black-box entry refresh tools to refresh dependent MVs,
records refresh intent in refreshes_entry, then invalidates cache tags.
Supports the soft/accept/idempotency lifecycle used by persona.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.refresh.types import RefreshResponse

# Black-box entry refresh tools — scenario-specific
from app.tools.entries.scenario_drafts.refresh import (
    refresh_scenario_drafts,
)
# Black-box entry refresh tools — shared infrastructure
from app.tools.entries.calls.refresh import refresh_calls_internal
from app.tools.entries.groups.refresh import refresh_groups
from app.tools.entries.group_names.refresh import refresh_group_names
from app.tools.entries.messages.refresh import refresh_messages_internal
from app.tools.entries.refreshes.create import create_refresh
from app.tools.entries.runs.refresh import refresh_runs_internal

# Tags to invalidate — artifact cache + resource caches
_TAGS = ["scenarios", "artifacts"]

# Views refreshed by this endpoint
ALL_TARGETS = [
    "scenario_drafts_mv",
    "runs_mv",
    "messages_mv",
    "calls_mv",
    "groups_mv",
    "group_names_mv",
]

_REFRESH_FNS = {
    "scenario_drafts_mv": refresh_scenario_drafts,
    "runs_mv": refresh_runs_internal,
    "messages_mv": refresh_messages_internal,
    "calls_mv": refresh_calls_internal,
    "groups_mv": refresh_groups,
    "group_names_mv": refresh_group_names,
}


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class RefreshScenarioApiRequest(BaseModel):
    """Request model for scenario refresh endpoint."""

    targets: list[str] | None = Field(
        None,
        description=(
            "MV targets to refresh (omit for all). Options: "
            "scenario_drafts_mv, runs_mv, messages_mv, calls_mv, groups_mv, group_names_mv"
        ),
    )

    idempotency_key: UUID | None = Field(None, description="Operation key for ack")
    accept: bool = Field(
        True,
        description="Accept or reject. Only meaningful with idempotency_key",
    )


async def _execute_refreshes(pool: asyncpg.Pool, targets: list[str], redis: Redis | None = None) -> None:
    """Execute MV refreshes in parallel for the given targets."""

    async def _refresh(target: str) -> None:
        fn = _REFRESH_FNS.get(target)
        if fn is not None:
            async with pool.acquire() as conn:
                await fn(conn, redis=redis)

    await asyncio.gather(*[_refresh(target) for target in targets])


async def _record_refreshes(
    pool: asyncpg.Pool,
    *,
    targets: list[str],
    operation_key: UUID,
    session_id: UUID,
) -> None:
    """Record refresh intent/execution in refreshes_entry."""
    async with pool.acquire() as conn:
        for target in targets:
            await create_refresh(
                conn,
                operation_key=operation_key,
                artifact_type="scenario",
                target=target,
                session_id=session_id,
            )


async def refresh_scenario_impl(
    pool: asyncpg.Pool,
    redis: Redis | None,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    request: RefreshScenarioApiRequest | None = None,
    targets: list[str] | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    operation_key: UUID | None = None,
    **_kwargs,
) -> RefreshResponse:
    """Scenario refresh using composable infra functions.

    Flow:
      1. resolve_profile_identity_context — permission check
      2. Determine targets
      3. Soft: record intent only. Accept: execute. Reject: no-op.
      4. Refresh dependent entry MVs
      5. Record in refreshes_entry
      6. Invalidate cache tags
    """
    if request is not None:
        targets = targets or request.targets
        idempotency_key = idempotency_key or request.idempotency_key
        if idempotency_key and accept is None:
            accept = request.accept

    effective_targets = targets or ALL_TARGETS
    effective_operation_key = operation_key or idempotency_key

    # ── Step 1: Permission check ─────────────────────────────────────────

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Short-circuit: ack path ──────────────────────────────────────────

    if accept is not None and idempotency_key is not None:
        if accept:
            await _execute_refreshes(pool, effective_targets, redis=redis)
            if session_id is not None and effective_operation_key is not None:
                await _record_refreshes(
                    pool,
                    targets=effective_targets,
                    operation_key=effective_operation_key,
                    session_id=session_id,
                )
            if redis is not None:
                from app.utils.cache.invalidate_tags import invalidate_tags

                await invalidate_tags(_TAGS, redis=redis)
        return RefreshResponse(
            success=True,
            refreshed_views=effective_targets if accept else [],
            invalidated_tags=_TAGS if accept else [],
            idempotency_key=idempotency_key,
        )

    # ── Step 2: Soft — record intent only ────────────────────────────────

    if soft:
        if session_id is not None and effective_operation_key is not None:
            await _record_refreshes(
                pool,
                targets=effective_targets,
                operation_key=effective_operation_key,
                session_id=session_id,
            )
        return RefreshResponse(
            success=True,
            refreshed_views=[],
            invalidated_tags=[],
            idempotency_key=effective_operation_key,
        )

    # ── Step 3: Refresh dependent entry MVs ──────────────────────────────

    await _execute_refreshes(pool, effective_targets, redis=redis)

    # ── Step 4: Record in refreshes_entry ────────────────────────────────

    if session_id is not None and effective_operation_key is not None:
        await _record_refreshes(
            pool,
            targets=effective_targets,
            operation_key=effective_operation_key,
            session_id=session_id,
        )

    # ── Step 5: Invalidate cache tags ────────────────────────────────────

    if redis is not None:
        from app.utils.cache.invalidate_tags import invalidate_tags

        await invalidate_tags(_TAGS, redis=redis)

    return RefreshResponse(
        success=True,
        refreshed_views=effective_targets,
        invalidated_tags=_TAGS,
        idempotency_key=effective_operation_key,
    )
