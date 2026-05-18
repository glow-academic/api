"""Test generate logic — per-artifact generation entry point.

Two paths:
  1. trace_id set → resolve trace context, run replay/generation against
     a historical run. Used per-card after a row has been materialized.
  2. trace_id absent → attempt-style kicker. Resolves the test group via
     the canonical ``resolve_group_impl``, then prepare + execute the
     LLM with ``operations`` as tools (e.g. ``test.invocation_create``).
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
from app.infra.generation.runner import run_generation_with_refresh
from app.infra.generation.prepare import prepare_generation
from app.infra.globals import get_internal_sio
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.test.trace_context import resolve_trace_context
from app.infra.websocket.generation_types import (
    ArtifactGenerateResponse,
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
    instructions: list[str] | None = None,
    modalities: list[str] | None = None,
    audios_id: UUID | None = None,
    conversation_id: UUID | None = None,
    trace_id: UUID | None = None,
    operations: list[str] | None = None,
    dangerous: bool = False,
    params: dict | None = None,
    group_id: UUID | str | None = None,
    wait_for_complete: bool | None = None,
    profile_id: UUID,
    profiles_id: UUID,
    session_id: UUID,
    sid: str,
) -> tuple[dict, UUID, bool, UUID | None]:
    """Resolve trace context → build a generate payload dict.

    Returns (payload_dict, group_id, is_dynamic, historical_run_id).
    """
    assert trace_id is not None
    if operations:
        raise HTTPException(
            status_code=422,
            detail=(
                "operations not supported when trace_id is set — context "
                "is derived from the trace's connection tables."
            ),
        )

    trace_ctx = await resolve_trace_context(conn, trace_id)

    # Group is the test's canonical group; the historical run lives there.
    resolved_group_id: UUID | None = None
    if trace_ctx.historical_run_id:
        from app.tools.entries.runs.get import get_run as _get_run
        run = await _get_run(conn, trace_ctx.historical_run_id)
        if run:
            resolved_group_id = run.group_id
    if resolved_group_id is None and group_id is not None:
        try:
            resolved_group_id = (
                group_id if isinstance(group_id, UUID) else UUID(str(group_id))
            )
        except Exception:
            resolved_group_id = None
    if resolved_group_id is None:
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
        "group_id": str(resolved_group_id),
        "instructions": instructions or [],
        "operations": [],
        "modalities": ["text"],
        "params": {
            "trace_id": str(trace_id),
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
            "trace_id": str(trace_id),
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
    return payload, resolved_group_id, trace_ctx.is_dynamic, trace_ctx.historical_run_id


async def generate_test_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    instructions: list[str] | None = None,
    modalities: list[str] | None = None,
    audios_id: UUID | None = None,
    conversation_id: UUID | None = None,
    trace_id: UUID | None = None,
    operations: list[str] | None = None,
    dangerous: bool = False,
    params: dict | None = None,
    group_id: UUID | str | None = None,
    wait_for_complete: bool | None = None,
    instructions_role: str = "user",
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

    if sid:
        resolved_sid = sid
    else:
        from app.infra.websocket.get_socket_owner import get_socket_owner
        resolved_sid = await get_socket_owner(str(profile_id)) or ""

    # ── trace-driven path (per-card replay/generation) ──────────────────
    if trace_id is not None:
        if profile.profiles_id is None:
            raise HTTPException(status_code=400, detail="Profile resource not found.")
        async with pool.acquire() as conn:
            (
                trace_payload,
                resolved_group_id,
                is_dynamic,
                historical_run_id,
            ) = await _build_trace_payload(
                conn,
                instructions=instructions,
                modalities=modalities,
                audios_id=audios_id,
                conversation_id=conversation_id,
                trace_id=trace_id,
                operations=operations,
                dangerous=dangerous,
                params=params,
                group_id=group_id,
                wait_for_complete=wait_for_complete,
                profile_id=profile_id,
                profiles_id=profile.profiles_id,
                session_id=session_id,
                sid=resolved_sid,
            )

        # is_dynamic=False → skip the LLM call. The model output we'll bind
        # via /test/run is the historical run's existing assistant turn.
        if not is_dynamic:
            return ArtifactGenerateResponse(
                group_id=str(resolved_group_id),
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
        return ArtifactGenerateResponse(group_id=str(resolved_group_id))

    # ── kicker path (post-start; mirrors /attempt/generate) ─────────────
    if profile.profiles_id is None:
        raise HTTPException(status_code=400, detail="Profile resource not found.")

    # dangerous=False → tool calls are soft (pending). dangerous=True → immediate.
    tool_soft = not dangerous


    # Canonical group resolve — same shape attempt uses.
    group_id_str = group_id
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
        instructions=instructions,
        instructions_role=instructions_role,
        operations=operations,
        dangerous=dangerous,
        params=params,
        modalities=modalities,
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
                # Skip history items threaded into the dispatch by
                # prepare.py — the panel already shows them via
                # group_get; re-emitting as live events produces
                # duplicate bubbles. New messages (system, developer,
                # current user instruction) have no _emit key and
                # default to True.
                if not msg.get("_emit", True):
                    continue
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role and content:
                    await internal_sio.emit(
                        f"{ARTIFACT_TYPE}.generate.text.complete",
                        {
                            "sid": resolved_sid,
                            "rooms": [str(profile_id)],
                            "artifact_type": ARTIFACT_TYPE,
                            "run_id": str(prepared.run_id),
                            "group_id": str(group_id_str),
                            "role": role,
                            "text": content,
                        },
                    )

        # ── Run (blocking by default; opt-in fire-and-forget via
        # ``wait_for_complete=False`` — pair with X_Watch).
        wait_for_complete = wait_for_complete
        if wait_for_complete is None:
            wait_for_complete = True

        run_result = await run_generation_with_refresh(
            pool, redis,
            prepared=prepared,
            sid=resolved_sid,
            tool_soft=tool_soft,
            artifact_type=ARTIFACT_TYPE,
            refresh_fn=None,
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            internal_sio=internal_sio,
            wait_for_complete=wait_for_complete,
        )
    except Exception as e:
        logger.exception(f"Test generation failed: {e}")
        raise

    return ArtifactGenerateResponse(
        group_id=str(group_id_str),
        run_id=str(prepared.run_id),
        idempotency_key=str(generated_key),
        produced_media=run_result.produced_media if run_result else [],
    )
