"""Internal impl for attempt_chat_silence — shared by WebSocket and HTTP.

Records conversation completion in DB and emits attempt.generate.audio.session_complete.

Soft/accept (RECORD-AND-HOLD): silence ends a LIVE voice session (DB completion +
adapter cleanup + emits) — there's no single row to stage dormant, so ``soft=True``
stores the intent (``{chat_id}``) in a pending ``soft_calls_entry`` and performs
nothing; the ack ({idempotency_key, accept}) performs the silence (accept) or
discards it (reject). ``soft=False`` performs immediately (original behavior).
Mirrors stop_attempt_impl. WS callers (no profile/session) skip the wrapper.
"""

import uuid as uuid_mod
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel

from app.infra.events.audit import build_audit_arguments, run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client
from app.infra.websocket.attempt_types import AttemptAudioEndedData
from app.infra.websocket.audio_lifecycle import cleanup_audio_session
from app.infra.websocket.session_store import get_session_by_chat_id
from app.tools.entries.attempt_conversation_completion.create import (
    create_attempt_conversation_completion,
)
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

ARTIFACT = "attempt"
OPERATION = "chat_silence"


class AudioStopInternalResult(BaseModel):
    """Structured result for audio stop orchestration."""

    chat_id: str
    stopped: bool = True
    idempotency_key: str | None = None
    denied: bool = False


async def _perform_silence(
    chat_id: str, sid: str, requester_profile_id: str | None = None
) -> AudioStopInternalResult:
    """End the live voice session: record completion, clean up, emit.

    AUTHZ / ownership (the R3 guard — mirrors ``chat_speak_impl``'s W1 owner
    check for the same in-memory ``AudioSession`` keyed by the same ``chat_id``):
    only the authenticated owner of the live session may silence it. A
    non-owner caller (or a caller with no resolved profile) is denied with NO
    side effect — no DB completion, no adapter cleanup, no emit — so an attacker
    can't tear down a victim's live voice session by supplying its ``chat_id``.
    ``AudioSession.profile_id`` is stored as a ``str`` (audio.py sets it from
    ``str(prepared.profile_id)``), so we compare stringified. Owner-only (no
    role-hierarchy bypass), matching chat_speak.
    """
    redis = get_redis_client()
    session = get_session_by_chat_id(str(chat_id))
    if not session:
        # Silence on a non-existent session is a no-op — the voice session
        # already ended or never started.
        logger.info(f"attempt_chat_silence: no session for chat_id={chat_id} (no-op)")
        return AudioStopInternalResult(chat_id=str(chat_id), stopped=False)

    # Fail-closed owner guard: deny (no teardown) if the caller doesn't own the
    # session. ``requester_profile_id is None`` only on legacy callers that
    # never resolved an identity; both edges now pass it, so a missing one means
    # we cannot prove ownership → deny.
    if requester_profile_id is None or str(requester_profile_id) != (
        session.profile_id or ""
    ):
        logger.warning(
            f"attempt_chat_silence: owner mismatch for chat_id={chat_id} "
            f"(requester={requester_profile_id}); denied (no teardown)"
        )
        return AudioStopInternalResult(
            chat_id=str(chat_id), stopped=False, denied=True
        )

    group_id = session.group_id

    if session.conversation_id and session.session_id:
        try:
            pool = get_pool()
            async with pool.acquire() as conn:
                await create_attempt_conversation_completion(
                    conn, redis,
                    conversation_id=uuid_mod.UUID(session.conversation_id),
                    session_id=uuid_mod.UUID(str(session.session_id)),
                    stop=True,
                )
        except Exception as e:
            logger.warning(f"Failed to record conversation completion: {e}")

    await cleanup_audio_session(session)

    internal_sio = get_internal_sio()
    await internal_sio.emit(
        "attempt.generate.audio.session_complete",
        {"group_id": group_id, "sid": sid},
    )
    await internal_sio.emit(
        "attempt.chat.voice_ended",
        AttemptAudioEndedData(
            sid=sid,
            chat_id=str(chat_id),
            group_id=group_id,
            success=True,
            message="Voice session stopped",
            rooms=[session.profile_id] if session.profile_id else None,
        ).model_dump(mode="json"),
    )
    return AudioStopInternalResult(chat_id=str(chat_id))


async def attempt_chat_silence_internal_impl(
    data: dict[str, Any],
) -> AudioStopInternalResult:
    """Run canonical audio stop orchestration for any surface.

    Required data keys: chat_id. Optional: sid, profile_id, session_id,
    idempotency_key, soft, accept.
    """
    chat_id = data.get("chat_id")
    if not chat_id:
        raise ValueError("Missing chat_id for attempt_chat_silence")
    sid = data.get("sid", "")

    profile_id = data.get("profile_id")
    session_id = data.get("session_id")
    soft = bool(data.get("soft", False))
    accept = data.get("accept")
    idempotency_key = data.get("idempotency_key")
    if isinstance(idempotency_key, str):
        idempotency_key = uuid_mod.UUID(idempotency_key)
    is_ack = accept is not None and idempotency_key is not None

    redis = get_redis_client()

    async def _run(call_id: uuid_mod.UUID | None = None) -> AudioStopInternalResult:
        # ── Short-circuit: ack — perform (accept) or discard (reject) ──
        if accept is not None and idempotency_key is not None:
            async with get_pool().acquire() as conn:
                entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
            if entry is None or entry.status != "pending" or entry.operation != OPERATION:
                raise HTTPException(status_code=404, detail="No pending silence for this call.")
            result = AudioStopInternalResult(chat_id=str(chat_id), stopped=False)
            if accept:
                result = await _perform_silence(str(chat_id), sid, profile_id)
            async with get_pool().acquire() as conn:
                await create_soft_call(
                    conn, redis, call_id=idempotency_key, artifact=ARTIFACT,
                    operation=OPERATION, artifact_id=entry.artifact_id,
                    status="accepted" if accept else "rejected",
                )
            result.idempotency_key = str(idempotency_key)
            return result

        # ── Soft propose: record intent, perform nothing ──
        if soft and call_id is not None:
            async with get_pool().acquire() as conn:
                await create_soft_call(
                    conn, redis, call_id=call_id, artifact=ARTIFACT,
                    operation=OPERATION, artifact_id=uuid_mod.UUID(str(chat_id)), status="pending",
                    patch={"chat_id": str(chat_id)},
                )
            return AudioStopInternalResult(chat_id=str(chat_id), stopped=False, idempotency_key=str(call_id))

        # ── Live: perform now ──
        result = await _perform_silence(str(chat_id), sid, profile_id)
        result.idempotency_key = str(call_id) if call_id else None
        return result

    # WS callers (no profile/session) can't satisfy can_audit → run directly.
    if not profile_id or not session_id:
        return await _run()

    from app.infra.attempt.group import group_attempt_impl
    group_result = await group_attempt_impl(
        get_pool(), redis,
        profile_id=uuid_mod.UUID(str(profile_id)), session_id=uuid_mod.UUID(str(session_id)),
        id_only=True,
    )

    return await run_artifact_operation_with_audit(
        get_pool(),
        redis,
        artifact=ARTIFACT,
        profile_id=uuid_mod.UUID(str(profile_id)),
        group_id=group_result.group_id,
        operation=OPERATION,
        runner=_run,
        arguments={"accept": accept} if is_ack else build_audit_arguments(data),
        operation_key=idempotency_key,  # idempotency replay gate
        session_id=uuid_mod.UUID(str(session_id)),
        entity_id=uuid_mod.UUID(str(chat_id)),
        response_model=AudioStopInternalResult,
    )
