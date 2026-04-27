"""Run completion — shared business logic called at the end of every
generation (text, audio, eval re-entry).

Pure business logic with injected dependencies (``emit``, ``conn``, ``redis``).
No socket handler registration, no module-level sio, no global I/O —
importable without triggering the socket tree. Callers invoke this
directly rather than via a top-level internal event.

Flow:
  1. Save assistant message + token counts
  2. resolve_run_completion (DB-based) — check if all agents done
  3. If generation_test_id → route to eval (rubric quality gate)
  4. If no eval → results already persisted, emit generation_complete
  5. Chat special case → attempt grade completion
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

    # Identity context — propagated through the pipeline
    profile_id_str = data.get("profile_id")
    profiles_id_str = data.get("profiles_id")
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
    input_tokens = data.get("input_text_tokens", 0)
    output_tokens = data.get("output_text_tokens", 0)

    # Step 1: Save assistant message + token counts
    try:
        if assistant_output:
            await persist_run_message(
                conn,
                run_id=run_uuid,
                session_id=session_id,
                role="assistant",
                content=assistant_output,
                upload_folder=upload_folder,
            )

        if input_tokens or output_tokens:
            await create_token(
                conn,
                run_id=run_uuid,
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

    # Step 3: All agents finished
    tool_results = data.get("tool_results") or []
    metadata = data.get("metadata") or {}
    generation_test_id = metadata.get("generation_test_id")

    # Step 4: Eval gate (idempotent — handles first pass and re-entry)
    # If a rubric eval was set up (generation_test_id exists):
    #   - First pass: eval not graded yet → route to test_proceed, return
    #   - Second pass (re-triggered by generation_ended): eval graded → fall through
    if generation_test_id:
        from app.tools.entries.test_grade.search import search_test_grades
        from app.tools.entries.test_invocation.search import (
            search_test_invocation_entries_internal,
        )

        # Check if eval has been graded by looking for grade records
        invocations, _total = await search_test_invocation_entries_internal(
            conn,
            test_ids=[uuid.UUID(generation_test_id)],
            limit=10,
        )
        invocation_ids = [inv.invocation_id for inv in invocations]

        grades = []
        if invocation_ids:
            grades = await search_test_grades(
                conn,
                invocation_ids=invocation_ids,
                bypass_mv=True,
            )

        if not grades:
            # First pass — eval not graded yet, route to eval
            logger.info(
                f"Run {run_id}: eval {generation_test_id} not graded yet, "
                f"routing to test_proceed"
            )
            await emit(
                [
                    internal_event(
                        "test.proceed.completed",
                        {
                            "sid": sid,
                            "test_id": generation_test_id,
                            "force_proceed": True,
                            "profile_id": profile_id_str,
                            "profiles_id": profiles_id_str,
                            "session_id": session_id_str,
                        },
                    )
                ]
            )
            return

        # Second pass — eval graded, fall through to emit completion
        logger.info(
            f"Run {run_id}: eval {generation_test_id} graded "
            f"({len(grades)} grades), proceeding to completion"
        )

    # Step 6: Chat/attempt post-processing — refresh attempt MVs + emit
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

    # Step 7: Emit the artifact-namespaced completion event — the per-artifact
    # forwarder under ws/output/<artifact>/generate/completed.py fans it to the client.
    completion_payload = build_run_complete_payload(
        sid=sid,
        artifact_type=artifact_type,
        group_id=group_id_str,
        run_id=run_id,
        tool_results=tool_results,
        metadata=metadata,
    )
    await emit(
        [
            internal_event(
                f"{artifact_type}.generate.completed",
                completion_payload,
            )
        ]
    )

    # Mirror the lifecycle to the SSE hub so http-sse clients (the
    # GenerationPanel) clear isGenerating. The socket.io path above only
    # reaches WS subscribers; SSE listeners receive their stream through
    # ``publish()``.
    try:
        from uuid import UUID as _UUID

        from app.infra.stream.emitter import emit_artifact_operation_finished

        run_uuid: _UUID | None = None
        try:
            run_uuid = _UUID(run_id) if run_id else None
        except (TypeError, ValueError):
            run_uuid = None
        group_uuid: _UUID | None = None
        try:
            group_uuid = _UUID(group_id_str) if group_id_str else None
        except (TypeError, ValueError):
            group_uuid = None

        await emit_artifact_operation_finished(
            artifact=artifact_type,
            operation="generate",
            arguments={},
            output=completion_payload,
            group_id=group_uuid,
            entity_id=run_uuid,
            call_id=run_uuid,
            tool_id=None,
            role="assistant",
        )
    except Exception:
        # SSE bridge is best-effort — never break the WS path on a
        # transport mirror failure.
        logger.exception("SSE mirror of generate.completed failed")


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
