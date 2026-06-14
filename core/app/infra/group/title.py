"""Group title — write operation that renames an existing group.

Split out of ``resolve_group_impl`` so the read (resolve) and write
(rename) paths have clean boundaries:

  - ``resolve_group_impl`` is now pure read (snapshot_key for SETNX-race
    convergence on a single group across concurrent fetches).
  - ``title_group_impl`` is the write — appends a ``group_names_entry``
    row. ``groups_mv``/``group_names_mv`` resolve to the latest active
    entry per group, so multiple renames collapse to whichever fired
    last.

Soft/ack semantics use the ``active`` column on ``group_names_entry``:
  - ``soft=True`` → row written with ``active=False`` (dormant).
    ``group_names_mv`` filters out inactive rows, so the displayed
    title is unchanged until the ack call promotes it.
  - ``accept=True`` + ``idempotency_key`` → ``ON CONFLICT (id) DO
    UPDATE SET active = EXCLUDED.active`` flips the dormant row to
    active. Same idempotency_key drives both calls.
  - ``accept=False`` + ``idempotency_key`` → no-op (the dormant row
    stays for audit; ``group_names_mv`` ignores it).
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.group.refresh import refresh_group_impl
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.entries.group_names.create import create_group_name

# R3: artifact types whose group chain is per-session-private (group → session
# → owner), not org-shared catalog. Renaming these is a write-IDOR if unscoped,
# so the ownership gate lives HERE in the shared impl — no per-artifact wrapper
# (system/title, WS system.group_name) can omit it. The test/attempt wrappers
# also gate; the check is owner-or-deny, so re-running it for a legitimate owner
# is idempotent (no double-deny). Catalog artifacts (provider, model, …) keep
# the unscoped behavior they had by design.
_OWNER_SCOPED_GROUP_ARTIFACTS = frozenset({"test", "attempt", "system"})


class TitleGroupRequest(BaseModel):
    """Shared request body — each artifact subclasses for OpenAPI naming."""

    group_id: UUID = Field(..., description="Group to rename")
    title: str = Field(..., description="New title (display name) for the group")
    idempotency_key: UUID | None = Field(
        None,
        description="Operation key for ack — promotes or rejects a dormant rename",
    )
    accept: bool = Field(
        True,
        description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key",
    )


class TitleGroupResponse(BaseModel):
    """Shared response body — each artifact subclasses for OpenAPI naming."""

    group_id: UUID = Field(..., description="The group that was renamed")
    group_name_id: UUID = Field(
        ..., description="UUID of the new group_names_entry row"
    )
    title: str = Field(..., description="The title that was set")
    idempotency_key: UUID | None = Field(
        None, description="Operation key echoed back"
    )


async def title_group_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    artifact_type: str,
    profile_id: UUID,
    session_id: UUID,
    request: TitleGroupRequest | None = None,
    group_id: UUID | None = None,
    title: str | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **_kwargs,
) -> TitleGroupResponse:
    """Rename an existing group by inserting/promoting a ``group_names_entry``."""
    if request is not None:
        group_id = request.group_id
        title = request.title
        idempotency_key = idempotency_key or request.idempotency_key
        if idempotency_key and accept is None:
            accept = request.accept

    if group_id is None or not title:
        raise HTTPException(
            status_code=400,
            detail="`group_id` and `title` are required.",
        )

    with timed("profile"):
        profile = await resolve_profile_identity_context(
            pool, profile_id, redis, session_id=session_id,
        )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # R3: gate owner-scoped (per-session-private) group renames here so no
    # wrapper can skip it (system/title delegates with no gate of its own).
    # Resolves group → session → owner and denies non-owners; idempotent for
    # the test/attempt wrappers that already gate. `profile` is the requester.
    if artifact_type in _OWNER_SCOPED_GROUP_ARTIFACTS:
        from app.infra.attempt.permissions import (
            enforce_attempt_access_by_group,
        )

        await enforce_attempt_access_by_group(
            pool, redis, group_id=group_id, requester=profile,
        )

    # ── Ack short-circuit ─────────────────────────────────────────────
    # Promotes the dormant row written by the original soft call. The
    # UPSERT ``ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active``
    # flips active=true (or stays false on reject).
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            name_result = await create_group_name(
                conn,
                redis, group_id=group_id,
                name=title,
                session_id=session_id,
                id=idempotency_key,
                soft=not accept,
            )
        if accept:
            await refresh_group_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
            )
        return TitleGroupResponse(
            group_id=group_id,
            group_name_id=name_result.id,
            title=title,
            idempotency_key=idempotency_key,
        )

    # ── Normal write path ────────────────────────────────────────────
    with timed("db_write"):
      async with pool.acquire() as conn:
        name_result = await create_group_name(
            conn,
            redis, group_id=group_id,
            name=title,
            session_id=session_id,
            id=idempotency_key,
            soft=soft,
        )

    # Soft writes skip MV refresh — the dormant row is already invisible
    # to ``group_names_mv`` (filters active=true), so refreshing wouldn't
    # change what the client sees. Saves an unnecessary cache invalidation.
    if not soft:
        with timed("refresh"):
            await refresh_group_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
            )

    return TitleGroupResponse(
        group_id=group_id,
        group_name_id=name_result.id,
        title=title,
        idempotency_key=idempotency_key,
    )
