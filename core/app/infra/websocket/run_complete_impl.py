"""Run completion — shared business logic called at the end of every
generation (text, audio).

Pure business logic with injected dependencies (``emit``, ``conn``, ``redis``).
No socket handler registration, no module-level sio, no global I/O —
importable without triggering the socket tree. Callers invoke this
directly rather than via a top-level internal event.

Flow (atomic — fires once per run):
  1. Save assistant message + token counts.
  2. resolve_run_completion (DB-based) — check if all agents done.
  3. If chat/attempt → ``_chat_post_complete`` refreshes the attempt
     MVs and emits attempt lifecycle events.
  4. The audit framework wrapping ``/<artifact>/generate`` emits the
     canonical ``<artifact>.generate.completed`` event.

No server-side grading / promotion / candidate merging. Tests created
by ``setup_generation_test`` (rubric-bearing agents) leave their
candidate writes pending in ``soft_calls_entry``; the client drives
the rest — grading via ``/test/generate`` per invocation, promote /
demote via ``/<artifact>/create`` with ``idempotency_key + accept``.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import asyncpg

from app.infra.websocket.generation_types import GenerationCompleteData
from app.infra.websocket.persist_run_message import persist_run_message
from app.infra.websocket.resolve_run_completion import resolve_run_completion
from app.infra.websocket.socket_event import EmitFn, internal_event
from app.tools.entries.tokens.create import create_token
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


def _table_name(target_type: str, target_name: str) -> str:
    """Derive DB table from run_tracker target: names → names_resource, contents → contents_entry."""
    suffix = "resource" if target_type == "resource" else "entry"
    return f"{target_name}_{suffix}"


def build_run_complete_payload(
    *,
    sid: str,
    artifact_type: str,
    group_id: str,
    run_id: str,
    tool_results: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the final generation completion payload for run completion."""
    return GenerationCompleteData(
        sid=sid,
        artifact_type=artifact_type,
        group_id=group_id,
        run_id=run_id,
        success=True,
        message=f"{artifact_type.capitalize()} generation completed",
        tool_results=tool_results,
        metadata=metadata,
    ).model_dump(mode="json")


async def run_complete_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
    conn: asyncpg.Connection,
    redis: Any,
    upload_folder: Path | None = None,
) -> None:
    """Handle run_complete — triage contested vs uncontested, promote or grade.

    All I/O dependencies are injected — no globals accessed.
    Callable from socket handler, API, or tests.
    """
    sid = data.get("sid", "")

    run_id = data.get("run_id")
    group_id_str = data.get("group_id", "")
    modality = data.get("modality", "text")
    artifact_type = data.get("artifact_type", "unknown")

    session_id_str = data.get("session_id")

    logger.info(
        f"run_complete - modality={modality}, group_id={group_id_str}, "
        f"input_tokens={data.get('input_text_tokens', 0)}, "
        f"output_tokens={data.get('output_text_tokens', 0)}"
    )

    # Audio continuation: the realtime session stays open across turns.
    # All we need to do is rotate the run_id so the next turn's events
    # hang off a fresh run. No rate-limit gate — the audio continuation
    # payload never carried request_limit, so it was always a no-op.
    if modality == "audio":
        if group_id_str:
            from app.infra.websocket.session_store import (
                get_session_by_group_id,
                rotate_run_id,
            )

            session = get_session_by_group_id(group_id_str)
            if session:
                new_run_id = str(uuid.uuid4())
                rotate_run_id(session, new_run_id)
                logger.info(
                    f"Audio session continuation - group_id={group_id_str}, "
                    f"new_run_id={new_run_id}"
                )
        return

    if not run_id or not session_id_str:
        return

    run_uuid = uuid.UUID(run_id)
    session_id = uuid.UUID(session_id_str)
    assistant_output = data.get("assistant_output") or ""
    reasoning_output = data.get("reasoning_output") or ""
    # ISO-8601 timestamp marking the first reasoning delta. Used to
    # back-date the reasoning ``messages_entry.created_at`` so the FE
    # can derive "Thought for Xs" from (answer.created_at − reasoning.created_at).
    # Without this, both rows land at run-complete time and the gap
    # collapses to ~ms.
    reasoning_started_at_raw = data.get("reasoning_started_at")
    reasoning_started_at = None
    if isinstance(reasoning_started_at_raw, str):
        from datetime import datetime as _dt
        try:
            reasoning_started_at = _dt.fromisoformat(reasoning_started_at_raw)
        except ValueError:
            reasoning_started_at = None
    input_tokens = data.get("input_text_tokens", 0)
    output_tokens = data.get("output_text_tokens", 0)

    # Step 1: Save assistant message + token counts. When the model
    # emitted a chain-of-thought trace, persist it as its OWN
    # messages_entry row (flagged reasoning=True) *before* the regular
    # assistant message so the two sort in the natural reasoning →
    # answer order. Each row is independently inactivatable / collapsible
    # by the FE.
    try:
        if reasoning_output:
            await persist_run_message(
                conn,
                redis,
                run_id=run_uuid,
                session_id=session_id,
                role="assistant",
                content=reasoning_output,
                upload_folder=upload_folder,
                reasoning=True,
                created_at=reasoning_started_at,
            )

        if assistant_output:
            await persist_run_message(
                conn,
                redis,
                run_id=run_uuid,
                session_id=session_id,
                role="assistant",
                content=assistant_output,
                upload_folder=upload_folder,
            )

        if input_tokens or output_tokens:
            await create_token(
                conn,
                redis, run_id=run_uuid,
                session_id=session_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
    except Exception as e:
        logger.exception(f"Failed to save run_complete for {artifact_type}: {e}")

    # Step 2: Check if all agents are done (DB-based, no Redis)
    group_id_uuid = uuid.UUID(group_id_str) if group_id_str else None
    if not group_id_uuid:
        logger.warning(f"No group_id in run_complete for {run_id}, skipping coordination")
        return

    completion = await resolve_run_completion(
        conn,
        run_id=run_uuid,
        group_id=group_id_uuid,
    )

    if not completion.all_done:
        return  # More agents pending

    # Step 3: All agents finished. ``setup_generation_test`` may have
    # created test+invocation scaffolding for rubric-bearing agents, but
    # nothing on the server promotes / grades / merges those candidates
    # automatically — that's all client-driven via the soft_calls_entry
    # ack pattern. Run completion is atomic: emit and stop. The client
    # decides whether to grade (fire ``/test/generate`` per invocation)
    # and which candidate to promote (call ``/<artifact>/create`` with
    # ``idempotency_key + accept``).
    metadata = data.get("metadata") or {}

    # Step 4: Chat/attempt post-processing — refresh attempt MVs + emit
    # attempt_chat_started / attempt_grade_complete before the final completion
    # event so downstream UI sees consistent state.
    if artifact_type in ("chat", "attempt"):
        await _chat_post_complete(
            emit=emit,
            conn=conn,
            redis=redis,
            sid=sid,
            artifact_type=artifact_type,
            metadata=metadata,
        )

    # Step 7: ``<artifact>.generate.completed`` is emitted by the audit
    # framework wrapping the ``/X/generate`` route — see
    # ``run_artifact_operation_with_audit`` in ``app/infra/events/audit.py``.
    # This impl previously fired its own copy here (back when the
    # generate path didn't go through audit), but the audit emit now
    # carries the canonical lifecycle event with tool envelope, group_id,
    # operation_key, etc. Firing here too produced duplicate
    # ``persona.generate.completed`` (and ``chat.generate.completed``,
    # etc.) on the wire. Single source of truth: the audit framework.


async def _chat_post_complete(
    *,
    emit: EmitFn,
    conn: asyncpg.Connection,
    redis: Any,
    sid: str,
    artifact_type: str,
    metadata: dict[str, Any],
) -> None:
    """Chat/attempt post-complete: refresh MVs + emit attempt lifecycle events.

    Called inline so no top-level dispatcher event is needed.
    """
    from app.infra.websocket.attempt_types import (
        AttemptChatStartedData,
        AttemptGradeCompleteData,
    )
    from app.tools.entries.attempt.refresh import refresh_attempt
    from app.tools.entries.attempt_chat.refresh import refresh_attempt_chat
    from app.utils.cache.invalidate_tags import invalidate_tags

    if artifact_type == "chat":
        attempt_id = metadata.get("attempt_id")
        attempt_chat_id = metadata.get("attempt_chat_id")
        if attempt_id and attempt_chat_id and not metadata.get("chat_started_emitted"):
            try:
                await refresh_attempt(conn)
                await refresh_attempt_chat(conn)
                await invalidate_tags(["attempt", "attempts"], redis=redis)
                await emit(
                    [
                        internal_event(
                            "attempt.chat_create.completed",
                            AttemptChatStartedData(
                                sid=sid,
                                attempt_id=attempt_id,
                                chat_id=attempt_chat_id,
                            ).model_dump(mode="json"),
                        )
                    ]
                )
            except Exception as e:
                logger.exception(f"Failed chat post-save: {e}")

    grade_id = metadata.get("grade_id")
    chat_id = metadata.get("chat_id")
    if grade_id and chat_id and not metadata.get("grade_complete_emitted"):
        try:
            await emit(
                [
                    internal_event(
                        "attempt.chat_grade.completed",
                        AttemptGradeCompleteData(
                            sid=sid,
                            chat_id=chat_id,
                            grade_id=grade_id,
                        ).model_dump(mode="json"),
                    )
                ]
            )
        except Exception as e:
            logger.exception(f"Failed attempt grade completion emit: {e}")
