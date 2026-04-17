"""Agent group logic — time-windowed artifact grouping.

Canonical infra function for resolving or creating agent groups.
Per-artifact, Redis-backed sliding window. Also supports explicit
group naming, replacing the need for the centralized group/name.py.

Flow:
  1. resolve_profile_identity_context -> profile
  2. Resolve group: existing (by group_id or Redis window) or create fresh
  3. Optional: create group_names_entry
  4. Refresh MVs + invalidate cache (only when something was written)
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.group.refresh import refresh_group_impl
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.group_names.create import create_group_name
from app.tools.entries.groups.create import create_group

ARTIFACT_TYPE = "agent"
DEFAULT_WINDOW_SECONDS = 60


def _redis_key(profile_id: UUID) -> str:
    return f"artifact_group:{ARTIFACT_TYPE}:{profile_id}"


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class GroupAgentApiRequest(BaseModel):
    """Request model for agent group endpoint."""

    group_id: UUID | None = Field(
        None,
        description="Existing group UUID (omit to create or reuse via time window)",
    )
    name: str | None = Field(None, description="Optional name for the group")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant group")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class GroupAgentApiResponse(BaseModel):
    """Response model for agent group endpoint."""

    group_id: UUID = Field(
        ..., description="Resolved or newly created group UUID"
    )
    group_name_id: UUID | None = Field(
        None,
        description="UUID of the created group_names entry (if name was provided)",
    )
    name: str | None = Field(
        None, description="The name that was set (if provided)"
    )
    idempotency_key: UUID | None = Field(
        None,
        description="Idempotency key echoed back for client correlation",
    )


# ---------------------------------------------------------------------------
# Impl
# ---------------------------------------------------------------------------


async def group_agent_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: GroupAgentApiRequest | None = None,
    group_id: UUID | None = None,
    name: str | None = None,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **_kwargs,
) -> GroupAgentApiResponse:
    """Resolve or create an agent group with optional naming.

    Behavior:
      - group_id omitted -> check Redis for active time-windowed group;
        create new groups_entry if none found.
      - group_id provided -> use it directly and refresh the window.
      - name provided -> create group_names_entry for the resolved group.

    Accepts either a GroupAgentApiRequest (HTTP/WS) or kwargs (internal).
    """
    # Unpack request if provided
    if request is not None:
        group_id = request.group_id
        name = request.name
        idempotency_key = idempotency_key or request.idempotency_key
        if idempotency_key and accept is None:
            accept = request.accept

    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                await create_group(
                    conn,
                    session_id=session_id,
                    artifact_type=ARTIFACT_TYPE,
                    id=idempotency_key,
                    soft=False,
                )
            await refresh_group_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
            )
        return GroupAgentApiResponse(
            group_id=idempotency_key,
            group_name_id=None,
            name=name,
            idempotency_key=idempotency_key,
        )

    # -- Step 1: Profile context --------------------------------------------

    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Resolve or create group ------------------------------------

    resolved_group_id: UUID
    created_new = False

    if group_id is not None:
        resolved_group_id = group_id
        # Refresh the window since this group is still active
        await redis.setex(
            _redis_key(profile_id), window_seconds, str(group_id),
        )
    else:
        # Check Redis time window
        key = _redis_key(profile_id)
        existing = await redis.get(key)
        if existing:
            resolved_group_id = UUID(
                existing.decode() if isinstance(existing, bytes) else existing
            )
            await redis.expire(key, window_seconds)
        else:
            async with pool.acquire() as conn:
                result = await create_group(
                    conn,
                    session_id=session_id,
                    artifact_type=ARTIFACT_TYPE,
                    id=idempotency_key,
                    soft=soft,
                )
            resolved_group_id = result.id
            await redis.setex(key, window_seconds, str(resolved_group_id))
            created_new = True

    # -- Step 3: Optional naming --------------------------------------------

    group_name_id: UUID | None = None
    if name:
        async with pool.acquire() as conn:
            name_result = await create_group_name(
                conn,
                group_id=resolved_group_id,
                name=name,
                session_id=session_id,
            )
            group_name_id = name_result.id

    if created_new or group_name_id:
        await refresh_group_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
        )

    return GroupAgentApiResponse(
        group_id=resolved_group_id,
        group_name_id=group_name_id,
        name=name,
        idempotency_key=idempotency_key or resolved_group_id,
    )
