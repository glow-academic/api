"""Internal handler: test_trace — create the trace bundle.

Pure setup: writes a test_invocation_traces_entry row binding to a
historical run_id and writes the per-turn bundle config to the trace's
connection tables. The client then calls /test/generate with the
returned trace_id.

No auto-inheritance from the parent test_invocation. The trace records
exactly what the caller passes; downstream readers do not fall back to
invocation-level defaults.

Free-text fields (``prompt_text``, ``instructions``) are minted via
canonical resource black boxes (``create_prompt`` / ``create_instruction``)
and the resulting ids are attached through the connection tables.

Soft/accept (RECORD-AND-HOLD): a trace mints multiple resources (prompts,
instructions) + a traces row + several connection tables, so rather than stage
all of them dormant we store the *intent* — the full payload — in a pending
``soft_calls_entry`` and perform nothing. The ack ({idempotency_key, accept})
replays the stored payload to actually create the trace (accept) or discards it
(reject). The payload contains everything needed, so this is lossless.
``soft=False`` creates immediately (original behavior).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.infra.events.audit import (
    build_audit_arguments,
    run_artifact_operation_with_audit,
)
from app.infra.globals import get_pool, get_redis_client
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.websocket.socket_event import EmitFn
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.test_invocation_traces.create import (
    create_test_invocation_traces,
)
from app.infra.invocation.refresh import refresh_invocation_impl
from app.infra.server_timing import timed
from app.tools.resources.instructions.create import create_instruction
from app.tools.resources.prompts.create import create_prompt

ARTIFACT = "test"
OPERATION = "trace"


class TestTracePayload(BaseModel):
    __test__ = False  # pytest: not a test class (domain model)
    """Client-to-server: open a trace on a test invocation.

    Bundle fields are stored verbatim on the trace's connection tables.
    No auto-inheritance from the parent test_invocation — caller passes
    whatever it wants the trace to record.

    Free-text fields are minted as new resource rows server-side and
    their ids are attached. Pre-minted ids can also be passed directly
    via ``prompt_ids`` / ``instruction_ids`` (combined with any minted
    from text).
    """

    test_id: UUID = Field(..., description="UUID of the test")
    test_invocation_id: UUID = Field(..., description="UUID of the test invocation")
    run_id: UUID | None = Field(
        None, description="Historical run_id we're replaying against (optional)"
    )

    # Direct id overrides — written verbatim to connection tables.
    tool_ids: list[UUID] | None = None
    modality_ids: list[UUID] | None = None
    voice_ids: list[UUID] | None = None
    temperature_level_ids: list[UUID] | None = None
    reasoning_level_ids: list[UUID] | None = None
    quality_ids: list[UUID] | None = None

    # Pre-minted ids — combined with the minted-from-text counterparts.
    prompt_ids: list[UUID] | None = None
    instruction_ids: list[UUID] | None = None

    # Free-text fields — server mints resource rows + attaches.
    prompt_text: str | None = Field(
        None, description="User-typed system prompt; minted as a prompts_resource"
    )
    instructions: list[str] | None = Field(
        None, description="User-typed instruction templates; each minted separately"
    )

    # Canonical idempotency + soft/accept (record-and-hold)
    idempotency_key: UUID | None = Field(None, description="Idempotency key — replays the prior call; on the ack, the server-minted soft key to perform/discard the staged trace")
    soft: bool = Field(False, description="Stage the trace (store intent without creating); accept performs it")
    accept: bool | None = Field(None, description="Ack: True performs the staged trace, False discards. Only meaningful with idempotency_key")


class TestTraceInternalResult(BaseModel):
    __test__ = False  # pytest: not a test class (domain model)
    test_invocation_trace_id: str
    success: bool = True
    idempotency_key: UUID | None = None


async def _perform_trace(
    payload: TestTracePayload, *, profile_id: str, session_id: str
) -> str:
    """Actually create the trace + bundle config. Returns the trace id."""
    pool = get_pool()
    redis = get_redis_client()
    with timed("db_write"):
        async with pool.acquire() as conn:
            prompt_ids: list[UUID] = list(payload.prompt_ids or [])
            if payload.prompt_text and payload.prompt_text.strip():
                minted_prompt = await create_prompt(
                    conn, system_prompt=payload.prompt_text, name="", description="", redis=redis,
                )
                prompt_ids.append(minted_prompt.id)

            instruction_ids: list[UUID] = list(payload.instruction_ids or [])
            for template in payload.instructions or []:
                if not template or not template.strip():
                    continue
                minted_instruction = await create_instruction(conn, template=template, redis=redis)
                instruction_ids.append(minted_instruction.id)

            result = await create_test_invocation_traces(
                conn, redis,
                test_invocation_id=payload.test_invocation_id,
                run_id=payload.run_id,
                instruction_ids=instruction_ids or None,
                prompt_ids=prompt_ids or None,
                tool_ids=payload.tool_ids,
                modality_ids=payload.modality_ids,
                voice_ids=payload.voice_ids,
                temperature_level_ids=payload.temperature_level_ids,
                reasoning_level_ids=payload.reasoning_level_ids,
                quality_ids=payload.quality_ids,
            )
    with timed("refresh"):
        await refresh_invocation_impl(
            pool, redis, profile_id=UUID(str(profile_id)), session_id=UUID(str(session_id)),
            targets=["test_invocation_traces_mv"],
        )
    return str(result.id)


async def test_trace_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> TestTraceInternalResult:
    """Insert a test_invocation_traces_entry row + bundle config."""
    payload = TestTracePayload(**data)
    sid = data.get("sid", "")

    profile_id = data.get("profile_id") or (
        await find_profile_by_socket(sid) if sid else None
    )
    if not profile_id:
        raise ValueError("Missing profile_id for test_trace")

    session_id = data.get("session_id") or (
        await find_session_by_socket(sid) if sid else None
    )
    if not session_id:
        raise ValueError("Missing session_id for test_trace")

    soft = payload.soft
    accept = payload.accept
    idempotency_key = payload.idempotency_key
    is_ack = accept is not None and idempotency_key is not None

    async def _run(call_id: UUID | None = None) -> TestTraceInternalResult:
        redis = get_redis_client()

        # ── Short-circuit: ack — perform (accept) or discard (reject) the staged trace ──
        if accept is not None and idempotency_key is not None:
            async with get_pool().acquire() as conn:
                entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
            if entry is None or entry.status != "pending" or entry.operation != OPERATION:
                raise HTTPException(status_code=404, detail="No pending trace for this call.")
            trace_id = ""
            if accept:
                stored = (entry.patch or {}).get("payload", {})
                trace_id = await _perform_trace(
                    TestTracePayload(**stored), profile_id=str(profile_id), session_id=str(session_id),
                )
            async with get_pool().acquire() as conn:
                await create_soft_call(
                    conn, redis, call_id=idempotency_key, artifact=ARTIFACT,
                    operation=OPERATION, artifact_id=entry.artifact_id,
                    status="accepted" if accept else "rejected",
                )
            return TestTraceInternalResult(
                test_invocation_trace_id=trace_id, idempotency_key=idempotency_key,
            )

        # ── Soft propose: record the full intent, create nothing ──
        if soft and call_id is not None:
            async with get_pool().acquire() as conn:
                await create_soft_call(
                    conn, redis, call_id=call_id, artifact=ARTIFACT,
                    operation=OPERATION, artifact_id=payload.test_invocation_id, status="pending",
                    patch={"payload": payload.model_dump(mode="json")},
                )
            return TestTraceInternalResult(test_invocation_trace_id="", idempotency_key=call_id)

        # ── Live: perform now ──
        trace_id = await _perform_trace(payload, profile_id=str(profile_id), session_id=str(session_id))
        return TestTraceInternalResult(test_invocation_trace_id=trace_id, idempotency_key=call_id)

    if not audit:
        return await _run()

    # Resolve the time-windowed test group so the wrapper mints a calls_entry
    # (``can_audit`` needs group_id) + threads its call_id.
    from app.infra.test.group import group_test_impl
    group_result = await group_test_impl(
        get_pool(), get_redis_client(),
        profile_id=UUID(str(profile_id)), session_id=UUID(str(session_id)), id_only=True,
    )

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact=ARTIFACT,
        profile_id=UUID(str(profile_id)),
        group_id=group_result.group_id,
        operation=OPERATION,
        runner=_run,
        arguments={"accept": accept} if is_ack else build_audit_arguments(data),
        operation_key=idempotency_key,  # idempotency replay gate
        session_id=UUID(str(session_id)),
        entity_id=payload.test_invocation_id,
        test_id=payload.test_id,
        response_model=TestTraceInternalResult,
    )
