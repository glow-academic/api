"""Test generate logic — per-artifact generation entry point.

Two paths:
  1. trace_id set → resolve trace context, run replay/generation against
     a historical run. Used per-card after a row has been materialized.
  2. trace_id absent → attempt-style kicker. Resolves the test group via
     the canonical ``resolve_group_impl``, then prepare + execute the
     LLM with ``cfg.operations`` as tools (e.g. ``test.invocation_create``).
     The model creates one test_invocation per call (one card at a time),
     mirroring how /attempt/generate drives /attempt/chat/create.

When trace_id is set, ``operations`` on the request is rejected — the
trace's connection tables are the source of truth.
"""

from __future__ import annotations

import uuid
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.generation.execute import execute_generation
from app.infra.generation.prepare import prepare_generation
from app.infra.globals import get_internal_sio
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.test.trace_context import resolve_trace_context
from app.infra.websocket.generation_types import (
    ArtifactGenerateRequest,
    ArtifactGenerateResponse,
    GenerateConfig,
    GeneratePayload,
)
from app.infra.websocket.socket_event import make_emit
from app.registry.generate import REGISTRY
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

ARTIFACT_TYPE = "test"


async def _build_trace_payload(
    conn: asyncpg.Connection,
    *,
    request: ArtifactGenerateRequest,
    profile_id: UUID,
    profiles_id: UUID,
    session_id: UUID,
    sid: str,
) -> tuple[dict, UUID, bool, UUID | None]:
    """Resolve trace context → build a generate payload dict.

    Returns (payload_dict, group_id, is_dynamic, historical_run_id).
    """
    assert request.trace_id is not None
    if request.config and request.config.operations:
        raise HTTPException(
            status_code=422,
            detail=(
                "operations not supported when trace_id is set — context "
                "is derived from the trace's connection tables."
            ),
        )

    trace_ctx = await resolve_trace_context(conn, request.trace_id)

    # Group is the test's canonical group; the historical run lives there.
    group_id: UUID | None = None
    if trace_ctx.historical_run_id:
        from app.tools.entries.runs.get import get_run as _get_run
        run = await _get_run(conn, trace_ctx.historical_run_id)
        if run:
            group_id = run.group_id
    if group_id is None and request.config and request.config.group_id:
        try:
            group_id = UUID(request.config.group_id)
        except Exception:
            group_id = None
    if group_id is None:
        raise HTTPException(
            status_code=400,
            detail="Cannot derive group_id from trace; provide config.group_id.",
        )

    payload = {
        "sid": sid,
        "artifact_type": ARTIFACT_TYPE,
        "profile_id": str(profile_id),
        "profiles_id": str(profiles_id),
        "session_id": str(session_id),
        "group_id": str(group_id),
        "instructions": request.instructions or [],
        "operations": [],
        "modalities": ["text"],
        "params": {
            "trace_id": str(request.trace_id),
            "test_invocation_id": str(trace_ctx.test_invocation_id),
            "test_id": str(trace_ctx.test_id),
            "historical_run_id": (
                str(trace_ctx.historical_run_id)
                if trace_ctx.historical_run_id else None
            ),
        },
        "metadata": {
            "test_id": str(trace_ctx.test_id),
            "test_invocation_id": str(trace_ctx.test_invocation_id),
            "trace_id": str(request.trace_id),
            "historical_run_id": (
                str(trace_ctx.historical_run_id)
                if trace_ctx.historical_run_id else None
            ),
            "trace_agent_ids": [str(a) for a in trace_ctx.agent_ids],
            "trace_instruction_ids": [str(i) for i in trace_ctx.instruction_ids],
            "trace_prompt_ids": [str(p) for p in trace_ctx.prompt_ids],
            "trace_tool_ids": [str(t) for t in trace_ctx.tool_ids],
            "trace_modality_ids": [str(m) for m in trace_ctx.modality_ids],
            "trace_voice_ids": [str(v) for v in trace_ctx.voice_ids],
        },
    }
    return payload, group_id, trace_ctx.is_dynamic, trace_ctx.historical_run_id


async def generate_test_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: ArtifactGenerateRequest,
    sid: str | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **_kwargs,
) -> ArtifactGenerateResponse:
    """Trigger test generation."""
    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    if profile is None:
        raise HTTPException(
            status_code=401, detail="Profile not found. Please sign in again.",
        )

    if not has_permission(profile.role_permissions, ARTIFACT_TYPE, "generate"):
        raise HTTPException(
            status_code=403, detail="You don't have permission to generate tests.",
        )

    resolved_sid = sid or f"http-{uuid.uuid4()}"
    cfg = request.config or GenerateConfig()

    # ── trace-driven path (per-card replay/generation) ──────────────────
    if request.trace_id is not None:
        if profile.profiles_id is None:
            raise HTTPException(status_code=400, detail="Profile resource not found.")
        async with pool.acquire() as conn:
            (
                trace_payload,
                group_id,
                is_dynamic,
                historical_run_id,
            ) = await _build_trace_payload(
                conn,
                request=request,
                profile_id=profile_id,
                profiles_id=profile.profiles_id,
                session_id=session_id,
                sid=resolved_sid,
            )

        # is_dynamic=False → skip the LLM call. The model output we'll bind
        # via /test/run is the historical run's existing assistant turn.
        if not is_dynamic:
            return ArtifactGenerateResponse(
                group_id=str(group_id),
                run_id=(str(historical_run_id) if historical_run_id else None),
            )

        # is_dynamic=True → run the LLM through the canonical pipeline.
        from app.infra.generation.run_from_payload import (
            run_generation_from_payload,
        )

        emit = make_emit()
        await run_generation_from_payload(
            trace_payload, emit=emit, pool=pool, redis=redis,
        )
        return ArtifactGenerateResponse(group_id=str(group_id))

    # ── kicker path (post-start; mirrors /attempt/generate) ─────────────
    if profile.profiles_id is None:
        raise HTTPException(status_code=400, detail="Profile resource not found.")

    # dangerous=False → tool calls are soft (pending). dangerous=True → immediate.
    tool_soft = not cfg.dangerous

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key and accept is None:
        accept = request.accept

    # Canonical group resolve — same shape attempt uses.
    group_id_str = cfg.group_id
    if not group_id_str:
        from app.infra.group.resolve import resolve_group_impl
        group_result = await resolve_group_impl(
            pool, redis,
            artifact_type=ARTIFACT_TYPE,
            profile_id=profile_id,
            session_id=session_id,
            include_history=False,
        )
        group_id_str = str(group_result.group_id)

    config = REGISTRY.get(ARTIFACT_TYPE)
    if not config:
        raise HTTPException(status_code=400, detail=f"No config for {ARTIFACT_TYPE}")

    generated_key = idempotency_key or uuid.uuid4()
    payload = GeneratePayload(
        artifact_type=ARTIFACT_TYPE,
        instructions=request.instructions,
        operations=cfg.operations,
        dangerous=cfg.dangerous,
        params=cfg.params,
        modalities=request.modalities,
    )

    try:
        prepared = await prepare_generation(
            pool, redis,
            profile_id=profile_id,
            profiles_id=profile.profiles_id,
            session_id=session_id,
            group_id=UUID(str(group_id_str)),
            artifact_type=ARTIFACT_TYPE,
            artifact_config=config,
            payload=payload,
        )

        logger.info(
            f"GENERATE_TEST: prepared run_id={prepared.run_id}, "
            f"dispatches={len(prepared.dispatches)}, "
            f"resource_types={prepared.resource_types}"
        )

        internal_sio = get_internal_sio()
        for dispatch in prepared.dispatches:
            for msg in dispatch.messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role and content:
                    await internal_sio.emit(
                        f"{ARTIFACT_TYPE}.generate.text.complete",
                        {
                            "sid": resolved_sid,
                            "rooms": [resolved_sid] if resolved_sid else [],
                            "artifact_type": ARTIFACT_TYPE,
                            "run_id": str(prepared.run_id),
                            "group_id": str(group_id_str),
                            "role": role,
                            "text": content,
                        },
                    )

        await execute_generation(
            pool, redis,
            prepared=prepared,
            sid=resolved_sid,
            tool_soft=tool_soft,
        )
    except Exception as e:
        logger.exception(f"Test generation failed: {e}")
        raise

    return ArtifactGenerateResponse(
        group_id=str(group_id_str),
        run_id=str(prepared.run_id),
        idempotency_key=str(generated_key),
    )
