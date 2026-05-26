"""System export logic — view-aware, canonical file-modality output.

Dispatches to per-view exports (activity, pricing, group, session, health)
under a single artifact-level endpoint. All views return the canonical
``{file_id, file_name, row_count}`` shape; client downloads via
``/api/system/download/{file_id}`` (BFF) → ``/system/file/download``.

Per-view byte extraction: every per-view impl returns a Pydantic envelope
with base64-encoded ``content``. We call those impls directly (skipping the
per-view route layer to avoid double auth/audit) and decode the base64 here.
"""

from __future__ import annotations

import base64
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.exports.file_modality import (
    accept_staged_export,
    extension_from_mime,
    stage_export_soft_call,
    wrap_bytes_as_file,
)


async def export_system_impl(
    pool: asyncpg.Pool,
    redis: Redis,  # type: ignore[type-arg]
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    view: str,
    target_session_id: UUID | None = None,
    group_id: UUID | None = None,
    mode: str | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    call_id: UUID | None = None,
    **_kwargs,
):
    """Dispatch on ``view`` and return canonical ``ExportSystemApiResponse``."""
    from app.infra.system.types import ExportSystemApiResponse

    # ── Short-circuit: ack — activate/reject a staged export ─────────────
    if accept is not None and idempotency_key is not None:
        file_id, file_name, row_count = await accept_staged_export(
            pool, redis, artifact="system",
            idempotency_key=idempotency_key, accept=accept,
        )
        return ExportSystemApiResponse(
            file_id=file_id, file_name=file_name, row_count=row_count,
            idempotency_key=idempotency_key,
        )

    if view == "activity":
        from app.infra.activity.export import export_activity_impl
        envelope = await export_activity_impl(pool, redis, profile_id=profile_id)
    elif view == "pricing":
        from app.infra.pricing.export import export_pricing_impl
        envelope = await export_pricing_impl(pool, redis, profile_id=profile_id)
    elif view == "group":
        if group_id is None:
            raise HTTPException(
                status_code=400,
                detail="group_id is required for view='group'.",
            )
        from app.infra.group.export import export_group_impl
        envelope = await export_group_impl(
            pool, redis, profile_id=profile_id, group_id=group_id,
        )
    elif view == "session":
        if target_session_id is None:
            raise HTTPException(
                status_code=400,
                detail="session_id (target) is required for view='session'.",
            )
        from app.infra.session.export import export_session_impl
        envelope = await export_session_impl(
            pool, redis, profile_id=profile_id, target_session_id=target_session_id,
        )
    elif view == "health":
        from app.infra.health.export import export_health_impl
        envelope = await export_health_impl(pool, redis, profile_id=profile_id)
    else:
        raise HTTPException(
            status_code=400, detail=f"Unknown system export view: {view!r}",
        )

    raw_b64 = getattr(envelope, "content", "") or ""
    bytes_ = base64.b64decode(raw_b64) if raw_b64 else b""
    mime_type = getattr(envelope, "mime_type", "application/zip") or "application/zip"
    row_count = int(getattr(envelope, "row_count", 0) or 0)

    wrapped = await wrap_bytes_as_file(
        pool,
        redis,
        content=bytes_,
        file_name_prefix=f"system_{view}_export",
        mime_type=mime_type,
        extension=extension_from_mime(mime_type),
        session_id=session_id,
        soft=soft,
    )
    if soft and call_id is not None:
        await stage_export_soft_call(
            pool, redis, artifact="system", call_id=call_id,
            wrapped=wrapped, row_count=row_count,
        )
    return ExportSystemApiResponse(
        file_id=wrapped.file_id, file_name=wrapped.file_name,
        row_count=row_count, idempotency_key=call_id,
    )
