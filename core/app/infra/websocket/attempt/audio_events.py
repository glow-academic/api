"""Audio generation event contract — canonical ``attempt.*`` event emits.

This module provides:
1. InternalBusAudioEmitter — concrete AudioEventEmitter that uses EmitFn
2. get_audio_emitter() — factory for use by the audio adapter singleton

The adapter (realtime.py) receives an AudioEventEmitter via its constructor,
keeping the infra layer decoupled from the socket layer.

Assistant transcript and tool call events emit canonical generate_text_* and
generate_call_* events (same shape as generate_artifact.py) so they flow
through the same downstream handlers. The session store provides the generation
context (sid, artifact_type, tool_output_schemas, etc.).

Events emitted:
  - attempt.chat.assistant_audio            — per-frame PCM16 for realtime playback
  - attempt.chat.assistant_audio.complete   — turn-done audios_id reference
  - attempt.chat.user_start / user_audio    — VAD + persisted user speech
  - attempt.generate.audio.start/complete/error/response_cancelled
                                            — assistant audio turn lifecycle
  - generate_text_start/progress/complete   — transcript (still legacy, 1B migration)
  - generate_call_start/progress/complete   — tool calls (still legacy, 1B migration)
  - generate_run_complete                   — run finished (core workflow, kept)
"""

import json
import uuid
from typing import Any

from app.infra.generation.emit import canonical_generation_event
from app.infra.websocket.session_store import get_session_by_group_id
from app.infra.websocket.socket_event import (
    EmitFn,
    internal_event,
    make_emit,
)
from app.infra.websocket.tool_call_utils import (
    parse_partial_json,
    resolve_output_fields,
)


def _canonical(ctx: dict[str, Any], sub: str, phase: str) -> str:
    """Canonical ``{artifact}.generate.{sub}.{phase}`` name from the session
    context, falling back to ``generate_error`` when ``artifact_type`` is
    missing (shouldn't happen — every AudioSession carries it).
    """
    artifact = ctx.get("artifact_type")
    if not artifact:
        return "generate_error"
    return canonical_generation_event(artifact, sub, phase)


class InternalBusAudioEmitter:
    """Concrete AudioEventEmitter that emits via EmitFn.

    Satisfies the AudioEventEmitter protocol defined in
    app.infra.websocket.adapters.audio.base. All events emitted use the
    canonical ``attempt.chat.*`` / ``attempt.generate.*`` names directly.
    """

    def __init__(self, *, emit: EmitFn) -> None:
        self._emit = emit

    def _session_context(self, group_id: str) -> dict[str, Any]:
        """Build canonical generate_text_* base payload from session store.

        Identity (``profile_id``, ``session_id``) is surfaced so downstream
        handlers — especially ``run_complete_impl`` — can keep the run on
        the owning identity instead of re-emitting ``generate`` with null
        profile_id, which bounces as "Profile not found. Please reconnect."
        This is the WS equivalent of HTTP auth middleware: the session store
        is the ambient identity context for realtime-initiated events.
        """
        session = get_session_by_group_id(group_id)
        if not session:
            return {
                "modality": "audio",
                "sid": "",
                "artifact_type": "",
                "resource_type": "",
                "run_id": "",
                "group_id": group_id,
                "profile_id": None,
                "session_id": None,
                "metadata": {},
            }
        return {
            "modality": "audio",
            "sid": session.sid,
            "artifact_type": session.artifact_type or "",
            "resource_type": session.resource_type or "",
            "run_id": session.run_id,
            "group_id": group_id,
            "profile_id": session.profile_id,
            "session_id": session.session_id,
            "metadata": session.metadata,
        }

    # -- Assistant audio (canonical attempt.* events) --

    async def on_audio_start(self, group_id: str) -> None:
        """Assistant started speaking — emits ``attempt.generate.audio.start``."""
        ctx = self._session_context(group_id)
        await self._emit(
            [
                internal_event(
                    "attempt.generate.audio.start",
                    {
                        **ctx,
                        "type": "start",
                        "event_type": "audio_start",
                    },
                )
            ]
        )

    async def on_audio_delta(self, group_id: str, audio: bytes) -> None:
        """Assistant audio chunk — fires ``attempt.chat.assistant_audio``
        with the raw PCM16 frame. The client's ``enqueue_audio_delta``
        decodes and pushes it into the playback ``AudioContext``.
        """
        session = get_session_by_group_id(group_id)
        chat_id = session.chat_id if session else ""
        sid = session.sid if session else ""
        await self._emit(
            [
                internal_event(
                    "attempt.chat.assistant_audio",
                    {
                        "sid": sid,
                        "chat_id": chat_id,
                        "group_id": group_id,
                        "audio": audio,
                    },
                ),
            ]
        )

    async def on_audio_complete(self, group_id: str) -> None:
        """Assistant finished speaking — emits ``attempt.generate.audio.complete``."""
        ctx = self._session_context(group_id)
        await self._emit(
            [
                internal_event(
                    "attempt.generate.audio.complete",
                    {
                        **ctx,
                        "type": "complete",
                        "event_type": "audio_complete",
                    },
                )
            ]
        )

    # -- Assistant transcript (emits canonical generate_text_* events) --

    async def on_transcript_start(self, group_id: str, item_id: str) -> None:
        """Assistant transcript started — emits ``attempt.generate.text.start``."""
        ctx = self._session_context(group_id)
        await self._emit(
            [
                internal_event(
                    _canonical(ctx, "text", "start"),
                    {
                        **ctx,
                        "type": "start",
                        "event_type": "text_start",
                    },
                )
            ]
        )

    async def on_transcript_delta(self, group_id: str, transcript: str) -> None:
        """Assistant transcript chunk — emits ``attempt.generate.text.progress``."""
        ctx = self._session_context(group_id)
        await self._emit(
            [
                internal_event(
                    _canonical(ctx, "text", "progress"),
                    {
                        **ctx,
                        "type": "progress",
                        "event_type": "text_delta",
                        "delta": transcript,
                        "accumulated_content": "",
                    },
                )
            ]
        )

    async def on_transcript_complete(
        self, group_id: str, item_id: str, transcript: str
    ) -> None:
        """Assistant transcript finalized — emits ``attempt.generate.text.complete``."""
        ctx = self._session_context(group_id)
        await self._emit(
            [
                internal_event(
                    _canonical(ctx, "text", "complete"),
                    {
                        **ctx,
                        "type": "complete",
                        "event_type": "text_complete",
                        "text": transcript,
                    },
                )
            ]
        )

    # -- Tool calls (emits canonical generate_call_* events) --

    async def on_tool_call_start(
        self, group_id: str, item_id: str, call_id: str, name: str
    ) -> None:
        """Tool call started — emits generate_call_start.

        Mirrors ``generate_artifact_impl.py``: the provider's ``call_id``
        (OpenAI ``call_<opaque>``) is kept as ``responses_call_id`` for
        sending back ``function_call_output``. Our internal UUID (used by
        ledger/receipt tracking and forwarded as the canonical ``call_id``
        on ``generate_call_complete``) is minted here.
        """
        internal_call_id = (
            str(uuid.uuid7()) if hasattr(uuid, "uuid7") else str(uuid.uuid4())
        )
        session = get_session_by_group_id(group_id)
        if session:
            session.tool_call_states[call_id] = {
                "call_id": internal_call_id,
                "responses_call_id": call_id,
                "tool_name": name,
                "arguments": "",
            }
        ctx = self._session_context(group_id)
        await self._emit(
            [
                internal_event(
                    _canonical(ctx, "call", "start"),
                    {
                        **ctx,
                        "modality": "call",
                        "type": "start",
                        "event_type": "tool_call_start",
                        "tool_call_id": call_id,
                    },
                )
            ]
        )

    async def on_tool_call_delta(
        self, group_id: str, call_id: str, arguments_delta: str
    ) -> None:
        """Tool call arguments streaming — emits generate_call_progress."""
        session = get_session_by_group_id(group_id)
        st: dict[str, Any] = {}
        parsed_args: dict[str, Any] | None = None
        resolved_fields: dict[str, Any] | None = None
        if session:
            st = session.tool_call_states.get(call_id, {})
            st["arguments"] = st.get("arguments", "") + arguments_delta
            parsed_args = parse_partial_json(st["arguments"])
            resolved_fields = resolve_output_fields(
                parsed_args, st.get("tool_name"), session.tool_output_schemas
            )
        ctx = self._session_context(group_id)
        await self._emit(
            [
                internal_event(
                    _canonical(ctx, "call", "progress"),
                    {
                        **ctx,
                        "modality": "call",
                        "type": "progress",
                        "event_type": "tool_call_delta",
                        "tool_call_id": call_id,
                        "delta": arguments_delta,
                        "tool_name": st.get("tool_name"),
                        "arguments_delta": arguments_delta,
                        "arguments": parsed_args,
                        "resolved_fields": resolved_fields,
                    },
                )
            ]
        )

    async def on_tool_call_complete(
        self, group_id: str, call_id: str, name: str, arguments: str
    ) -> None:
        """Tool call arguments finalized — emits generate_call_complete."""
        session = get_session_by_group_id(group_id)
        try:
            arguments_dict = json.loads(arguments) if arguments else {}
        except json.JSONDecodeError:
            arguments_dict = {}
        resolved_fields: dict[str, Any] | None = None
        st: dict[str, Any] = {}
        if session:
            st = session.tool_call_states.get(call_id, {})
            resolved_fields = resolve_output_fields(
                arguments_dict, name, session.tool_output_schemas
            )
            session.tool_call_states.pop(call_id, None)
        internal_call_id = st.get("call_id") or (
            str(uuid.uuid7()) if hasattr(uuid, "uuid7") else str(uuid.uuid4())
        )
        ctx = self._session_context(group_id)
        await self._emit(
            [
                internal_event(
                    _canonical(ctx, "call", "complete"),
                    {
                        **ctx,
                        "modality": "call",
                        "type": "complete",
                        "event_type": "tool_call_complete",
                        "tool_call_id": call_id,
                        "tool_name": name,
                        "arguments": arguments_dict,
                        "arguments_delta": arguments,
                        "call_id": internal_call_id,
                        "responses_call_id": st.get("responses_call_id", call_id),
                        "resolved_fields": resolved_fields,
                    },
                )
            ]
        )

    # -- User speech --

    async def on_user_speech_start(self, group_id: str, item_id: str) -> None:
        """VAD detected user started speaking."""
        ctx = self._session_context(group_id)
        await self._emit(
            [
                internal_event(
                    "attempt.chat.user_start",
                    {
                        "sid": ctx.get("sid", ""),
                        "chat_id": (
                            get_session_by_group_id(group_id).chat_id
                            if get_session_by_group_id(group_id)
                            else ""
                        ),
                        "item_id": item_id,
                    },
                )
            ]
        )

    async def on_user_audio(
        self,
        group_id: str,
        *,
        audios_id: str,
        duration_ms: int,
    ) -> None:
        """User speech persisted via the canonical audio upload chain —
        emit the resource-level ``audios_id`` so the client can immediately
        run STT + chat_message without any promotion step.
        """
        session = get_session_by_group_id(group_id)
        chat_id = session.chat_id if session else ""
        sid = session.sid if session else ""
        await self._emit(
            [
                internal_event(
                    "attempt.chat.user_audio",
                    {
                        "sid": sid,
                        "chat_id": chat_id,
                        "group_id": group_id,
                        "audios_id": audios_id,
                        "duration_ms": duration_ms,
                    },
                )
            ]
        )

    async def on_assistant_audio(
        self,
        group_id: str,
        *,
        audios_id: str,
        duration_ms: int,
    ) -> None:
        """Assistant turn complete — emit ``attempt.chat.assistant_audio.complete``
        carrying the persisted ``audios_id`` so the client can attach the
        full clip to the assistant's chat_message (transcript arrives via
        ``attempt.generate.text.complete``). The per-frame bytes already
        streamed via ``attempt.chat.assistant_audio`` for playback.
        """
        session = get_session_by_group_id(group_id)
        chat_id = session.chat_id if session else ""
        sid = session.sid if session else ""
        await self._emit(
            [
                internal_event(
                    "attempt.chat.assistant_audio.complete",
                    {
                        "sid": sid,
                        "chat_id": chat_id,
                        "group_id": group_id,
                        "audios_id": audios_id,
                        "duration_ms": duration_ms,
                    },
                )
            ]
        )

    # -- Lifecycle --

    async def on_error(self, group_id: str, error_message: str) -> None:
        """Adapter or provider error — emits ``attempt.generate.audio.error``."""
        ctx = self._session_context(group_id)
        await self._emit(
            [
                internal_event(
                    "attempt.generate.audio.error",
                    {
                        **ctx,
                        "type": "error",
                        "event_type": "audio_error",
                        "error_message": error_message,
                    },
                )
            ]
        )

    async def on_response_cancelled(
        self, group_id: str, usage: dict[str, Any] | None = None
    ) -> None:
        """Provider response cancelled (barge-in) — emits ``attempt.generate.audio.response_cancelled``."""
        usage = usage or {}
        ctx = self._session_context(group_id)
        await self._emit(
            [
                internal_event(
                    "attempt.generate.audio.response_cancelled",
                    {
                        **ctx,
                        "input_text_tokens": usage.get("input_tokens", 0),
                        "output_text_tokens": usage.get("output_tokens", 0),
                    },
                )
            ]
        )

    async def on_response_done(
        self, group_id: str, usage: dict[str, Any] | None = None
    ) -> None:
        """Provider response completed — emits ``generate_run_complete``.

        ``generate_run_complete`` is the core dispatch-workflow event (run
        finalization, rate-limit gating, run_id rotation), intentionally
        left on its legacy name until the dispatch rewrite. The legacy
        ``generate_audio_response_done`` fanout (no subscribers) is gone.
        """
        usage = usage or {}
        ctx = self._session_context(group_id)

        await self._emit(
            [
                internal_event(
                    "generate_run_complete",
                    {
                        **ctx,
                        "type": "complete",
                        "event_type": "run_complete",
                        "input_text_tokens": usage.get("input_tokens", 0),
                        "output_text_tokens": usage.get("output_tokens", 0),
                        "assistant_output": "",
                        "tool_results": [],
                        "save": False,
                    },
                ),
            ]
        )


def get_audio_emitter() -> InternalBusAudioEmitter:
    """Factory for the audio event emitter singleton."""
    return InternalBusAudioEmitter(emit=make_emit())
