"""Audio generation event contract — all generate_audio_* events in one place.

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
  - generate_audio_start/progress/complete  — assistant audio (canonical audio events)
  - generate_text_start/progress/complete   — assistant transcript (canonical text events)
  - generate_call_start/progress/complete   — tool calls (canonical call events)
  - generate_run_complete                   — run finished (triggers rate limit + run_id rotation)
  - generate_audio_user_speech_start        — VAD detected user speaking
  - generate_audio_user_speech_delta        — user speech transcript chunk
  - generate_audio_user_speech_complete     — user speech finalized
  - generate_audio_error                    — adapter or provider error
  - generate_audio_response_done            — provider response completed
"""

import json
from typing import Any

from app.infra.websocket.session_store import get_session_by_group_id
from app.infra.websocket.socket_event import EmitFn, internal_event, make_emit
from app.infra.websocket.tool_call_utils import (
    parse_partial_json,
    resolve_output_fields,
)


class InternalBusAudioEmitter:
    """Concrete AudioEventEmitter that emits via EmitFn.

    Satisfies the AudioEventEmitter protocol defined in
    app.infra.websocket.adapters.audio.base.
    """

    def __init__(self, *, emit: EmitFn) -> None:
        self._emit = emit

    def _session_context(self, group_id: str) -> dict[str, Any]:
        """Build canonical generate_text_* base payload from session store."""
        session = get_session_by_group_id(group_id)
        if not session:
            return {
                "modality": "audio",
                "sid": "",
                "artifact_type": "",
                "resource_type": "",
                "run_id": "",
                "group_id": group_id,
                "metadata": {},
            }
        return {
            "modality": "audio",
            "sid": session.sid,
            "artifact_type": session.artifact_type or "",
            "resource_type": session.resource_type or "",
            "run_id": session.run_id,
            "group_id": group_id,
            "metadata": session.metadata,
        }

    # -- Assistant audio (emits canonical generate_audio_* events) --

    async def on_audio_start(self, group_id: str) -> None:
        """Assistant started speaking — emits generate_audio_start."""
        ctx = self._session_context(group_id)
        await self._emit(
            [
                internal_event(
                    "generate_audio_start",
                    {
                        **ctx,
                        "type": "start",
                        "event_type": "audio_start",
                    },
                )
            ]
        )

    async def on_audio_delta(self, group_id: str, audio: bytes) -> None:
        """Assistant audio chunk — emits generate_audio_progress."""
        await self._emit(
            [
                internal_event(
                    "generate_audio_progress",
                    {"group_id": group_id, "audio": audio},
                )
            ]
        )

    async def on_audio_complete(self, group_id: str) -> None:
        """Assistant finished speaking — emits generate_audio_complete."""
        ctx = self._session_context(group_id)
        await self._emit(
            [
                internal_event(
                    "generate_audio_complete",
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
        """Assistant transcript started — emits generate_text_start."""
        ctx = self._session_context(group_id)
        await self._emit(
            [
                internal_event(
                    "generate_text_start",
                    {
                        **ctx,
                        "type": "start",
                        "event_type": "text_start",
                    },
                )
            ]
        )

    async def on_transcript_delta(self, group_id: str, transcript: str) -> None:
        """Assistant transcript chunk — emits generate_text_progress."""
        ctx = self._session_context(group_id)
        await self._emit(
            [
                internal_event(
                    "generate_text_progress",
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
        """Assistant transcript finalized — emits generate_text_complete."""
        ctx = self._session_context(group_id)
        await self._emit(
            [
                internal_event(
                    "generate_text_complete",
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
        """Tool call started — emits generate_call_start."""
        session = get_session_by_group_id(group_id)
        if session:
            session.tool_call_states[call_id] = {
                "call_id": call_id,
                "tool_name": name,
                "arguments": "",
            }
        ctx = self._session_context(group_id)
        await self._emit(
            [
                internal_event(
                    "generate_call_start",
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
                    "generate_call_progress",
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
        if session:
            resolved_fields = resolve_output_fields(
                arguments_dict, name, session.tool_output_schemas
            )
            session.tool_call_states.pop(call_id, None)
        ctx = self._session_context(group_id)
        await self._emit(
            [
                internal_event(
                    "generate_call_complete",
                    {
                        **ctx,
                        "modality": "call",
                        "type": "complete",
                        "event_type": "tool_call_complete",
                        "tool_call_id": call_id,
                        "tool_name": name,
                        "arguments": arguments_dict,
                        "arguments_delta": arguments,
                        "call_id": call_id,
                        "resolved_fields": resolved_fields,
                    },
                )
            ]
        )

    # -- User speech --

    async def on_user_speech_start(self, group_id: str, item_id: str) -> None:
        """VAD detected user started speaking."""
        await self._emit(
            [
                internal_event(
                    "generate_audio_user_speech_start",
                    {"group_id": group_id, "item_id": item_id},
                )
            ]
        )

    async def on_user_speech_delta(
        self, group_id: str, item_id: str, transcript: str
    ) -> None:
        """User speech transcript chunk."""
        await self._emit(
            [
                internal_event(
                    "generate_audio_user_speech_delta",
                    {
                        "group_id": group_id,
                        "item_id": item_id,
                        "transcript": transcript,
                    },
                )
            ]
        )

    async def on_user_speech_complete(
        self,
        group_id: str,
        item_id: str,
        transcript: str,
        *,
        audio: bytes | None = None,
    ) -> None:
        """User speech finalized — triggers DB write in domain translator."""
        payload: dict[str, Any] = {
            "group_id": group_id,
            "item_id": item_id,
            "transcript": transcript,
        }
        if audio:
            payload["audio"] = audio
        await self._emit(
            [
                internal_event(
                    "generate_audio_user_speech_complete",
                    payload,
                )
            ]
        )

    # -- Lifecycle --

    async def on_error(self, group_id: str, error_message: str) -> None:
        """Adapter or provider error."""
        await self._emit(
            [
                internal_event(
                    "generate_audio_error",
                    {"group_id": group_id, "error_message": error_message},
                )
            ]
        )

    async def on_response_cancelled(
        self, group_id: str, usage: dict[str, Any] | None = None
    ) -> None:
        """Provider response cancelled (barge-in) — emits generate_audio_response_cancelled."""
        usage = usage or {}
        ctx = self._session_context(group_id)
        await self._emit(
            [
                internal_event(
                    "generate_audio_response_cancelled",
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
        """Provider response completed — emits generate_run_complete + generate_audio_response_done."""
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
                internal_event(
                    "generate_audio_response_done",
                    {"group_id": group_id, "usage": usage},
                ),
            ]
        )


def get_audio_emitter() -> InternalBusAudioEmitter:
    """Factory for the audio event emitter singleton."""
    return InternalBusAudioEmitter(emit=make_emit())
