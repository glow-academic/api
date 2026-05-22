"""Attempt stop — cancel an active generation.

Cancels in-flight realtime/result/run state for a given group_id.

Soft/accept (record-and-hold — stop is an *action*, not a stageable row):
``soft=True`` records the stop intent in a pending ``soft_calls_entry`` (keyed by
the audit server ``call_id``) WITHOUT cancelling — for composing a stop into a
dormant benchmark scenario; ``accept=True`` performs the cancel, ``accept=False``
discards. ``soft=False`` cancels immediately (the live path). Same record-and-hold
shape as refresh / unemulate. The cancel helpers are each idempotent (no-op if
nothing active), so replaying the live path is safe too.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.websocket.cancel_active_result import cancel_active_result
from app.infra.websocket.cancel_active_run import cancel_active_run
from app.infra.websocket.cancel_realtime_turn import cancel_realtime_turn
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call

ARTIFACT = "attempt"
OPERATION = "stop"


class AttemptStopRequest(BaseModel):
    group_id: UUID
    idempotency_key: UUID | None = Field(
        None,
        description="Idempotency key — replays the prior call; on the ack, set to "
        "the server-minted soft key to perform/reject a staged stop",
    )
    soft: bool = Field(
        False,
        description="Stage the stop (record the intent without cancelling) — for "
        "composing a stop into a dormant benchmark scenario; accept performs it",
    )
    accept: bool | None = Field(
        None,
        description="Ack: True performs the staged stop, False discards. Only "
        "meaningful with idempotency_key",
    )


class AttemptStopResponse(BaseModel):
    success: bool
    idempotency_key: UUID | None = Field(
        None,
        description="Server-minted soft-call key (audit call_id). On a soft propose, "
        "echo this back with accept to perform/reject the staged stop.",
    )


async def _cancel(group_id: UUID) -> None:
    gid = str(group_id)
    await cancel_active_result(gid)
    await cancel_active_run(gid)
    await cancel_realtime_turn(gid)


async def stop_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    call_id: UUID | None = None,
) -> AttemptStopResponse:
    """Cancel an active generation by group_id, with soft/accept staging."""
    # ── Short-circuit: ack — perform / discard the staged stop ──
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != OPERATION:
            raise HTTPException(status_code=404, detail="No pending stop for this call.")
        if accept:
            await _cancel(entry.artifact_id)
        async with pool.acquire() as conn:
            await create_soft_call(
                conn, redis, call_id=idempotency_key, artifact=ARTIFACT,
                operation=OPERATION, artifact_id=entry.artifact_id,
                status="accepted" if accept else "rejected",
            )
        return AttemptStopResponse(success=True, idempotency_key=idempotency_key)

    # ── Propose (soft): record the intent, do NOT cancel ──
    if soft and call_id is not None and group_id is not None:
        async with pool.acquire() as conn:
            await create_soft_call(
                conn, redis, call_id=call_id, artifact=ARTIFACT, operation=OPERATION,
                artifact_id=group_id, status="pending",
                patch={"group_id": str(group_id)},
            )
        return AttemptStopResponse(success=True, idempotency_key=call_id)

    # ── Immediate (soft=False): cancel now (original behavior) ──
    if group_id is not None:
        await _cancel(group_id)
    return AttemptStopResponse(success=True, idempotency_key=call_id)
