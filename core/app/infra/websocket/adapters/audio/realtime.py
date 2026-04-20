"""Realtime audio adapter for voice mode (OpenAI-compatible protocol).

This adapter connects to any OpenAI-compatible Realtime API via WebSocket and
handles bidirectional audio streaming between the client and the provider.

Supports OpenAI direct, Azure, xAI, Gemini, litellm proxy, or any provider
that implements the OpenAI Realtime WebSocket protocol (session.update,
input_audio_buffer.append, etc.) — just set the appropriate base_url.

Architecture:
- Uplink loop: Consumes from session.inbound_queue, sends to provider WebSocket
- Downlink loop: Receives from provider WebSocket, calls emitter callbacks

The adapter uses the server-side WebSocket approach (not WebRTC ephemeral keys)
to maintain control over the connection and enable server-side processing.
"""

import asyncio
import base64
import json
import logging
import uuid as uuid_mod
from typing import Any, Literal
from uuid import UUID

import websockets
from websockets.asyncio.client import ClientConnection

from app.infra.attempt.audio_upload import audio_upload_attempt_impl
from app.infra.globals import get_pool, get_redis_client
from app.infra.upload_paths import ensure_upload_subdir
from app.infra.websocket.adapters.audio.base import (
    AudioEventEmitter,
    AudioSessionConfig,
    BaseAudioAdapter,
)
from app.infra.websocket.session_store import AudioSession

logger = logging.getLogger(__name__)


def _pcm_to_wav_bytes(pcm_bytes: bytes) -> bytes:
    """Wrap raw 24 kHz mono PCM16 samples in a RIFF/WAV container.

    The realtime provider sends us raw samples; transcription / playback
    elsewhere needs a self-describing format. Small header, no resample.
    """
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)         # mono
        w.setsampwidth(2)         # 16-bit PCM
        w.setframerate(24000)     # provider-configured sample rate
        w.writeframes(pcm_bytes)
    return buf.getvalue()


async def _persist_realtime_audio(
    *,
    session: AudioSession,
    pcm_bytes: bytes,
    duration_ms: int,
    side: str,
) -> UUID:
    """Persist a captured PCM16 turn through the canonical audio upload chain.

    Wraps the raw samples in WAV, then calls ``audio_upload_attempt_impl``
    which creates the full ``uploads_entry → audios_resource →
    audios_entry → audios_audios_connection → audio_uploads_entry`` chain
    and returns the resource-level ``audios_id`` clients use for STT,
    attaching to messages, download, etc.

    ``side`` is purely for the auto-generated library name (``user`` or
    ``assistant``) so the admin UI can tell turn sides apart.
    """
    if not session.session_id:
        raise RuntimeError(
            "AudioSession missing session_id — cannot persist audio"
        )
    if not session.profile_id:
        raise RuntimeError(
            "AudioSession missing profile_id — cannot persist audio"
        )

    wav_bytes = _pcm_to_wav_bytes(pcm_bytes)
    length_seconds = max(0, duration_ms // 1000)
    filename = f"{side}-{uuid_mod.uuid4()}.wav"
    name = f"{side}-{session.conversation_id or session.chat_id}"

    # Make sure the target folder exists (audio_upload_attempt_impl writes
    # under AUDIO_FOLDER which is the same location).
    ensure_upload_subdir("audio")

    result = await audio_upload_attempt_impl(
        get_pool(),
        get_redis_client(),
        profile_id=UUID(session.profile_id),
        session_id=UUID(session.session_id),
        file_bytes=wav_bytes,
        filename=filename,
        content_type="audio/wav",
        length_seconds=length_seconds,
        name=name,
        description=f"Realtime {side} speech turn",
    )
    return result.audios_id

# Default Realtime API endpoint (OpenAI direct)
DEFAULT_REALTIME_URL = "wss://api.openai.com/v1/realtime"

# Default model for realtime
DEFAULT_REALTIME_MODEL = "gpt-4o-realtime-preview-2024-12-17"


class RealtimeAudioAdapter(BaseAudioAdapter):
    """Provider-generic Realtime API adapter using WebSocket connection.

    This adapter maintains a WebSocket connection to any OpenAI-compatible
    Realtime API and handles bidirectional audio streaming. Set base_url
    to point at OpenAI, Azure, xAI, Gemini, a litellm proxy, etc.
    """

    def __init__(self, emitter: AudioEventEmitter) -> None:
        super().__init__(emitter)
        self._tasks: dict[
            str, list[asyncio.Task[Any]]
        ] = {}  # group_id -> [uplink_task, downlink_task]

    def get_implementation_type(self) -> Literal["webrtc", "websocket"]:
        """This adapter uses WebSocket (server-side connection)."""
        return "websocket"

    async def initialize_session(
        self,
        session: AudioSession,
        api_key: str,
        base_url: str | None = None,
        model: str | None = None,
        voice: str | None = None,
        instructions: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AudioSessionConfig:
        """Initialize a realtime session with the provider.

        Establishes WebSocket connection and starts uplink/downlink loops.

        Args:
            session: The AudioSession containing queues and metadata
            api_key: Decrypted API key for the provider
            base_url: Provider's realtime WebSocket endpoint (defaults to OpenAI)
            model: Model to use (defaults to gpt-4o-realtime-preview)
            voice: Voice for TTS (e.g., "alloy", "echo", "shimmer")
            instructions: System instructions for the session
            tools: Tools available to the model
            **kwargs: Additional options (turn_detection, etc.)

        Returns:
            AudioSessionConfig with session details
        """
        model = model or DEFAULT_REALTIME_MODEL
        voice = voice or "alloy"

        # Guard against double-open: if the conversation already has a live
        # WS (multi-generate-per-conversation), reuse it. This is the cheap
        # half of session-reuse — per-turn binding updates happen elsewhere.
        if session.oa_ws_connection is not None:
            logger.info(
                "Reusing existing Realtime WS for group_id=%s conversation_id=%s",
                session.group_id,
                session.conversation_id,
            )
            return AudioSessionConfig(
                model=model,
                voice=voice,
                instructions=instructions,
                tools=tools,
                turn_detection=kwargs.get("turn_detection"),
            )

        # Build WebSocket URL from base_url (supports any provider).
        # Providers (including our LiteLLM proxy) are typically configured
        # with an http(s):// base URL — swap the scheme to ws(s):// here so
        # the same base is usable for both REST and realtime endpoints.
        ws_base = base_url or DEFAULT_REALTIME_URL
        if ws_base.startswith("http://"):
            ws_base = "ws://" + ws_base[len("http://"):]
        elif ws_base.startswith("https://"):
            ws_base = "wss://" + ws_base[len("https://"):]
        # If the base is a bare host (no realtime path), append the canonical
        # OpenAI-compatible realtime path. LiteLLM proxy exposes realtime at
        # /v1/realtime just like OpenAI.
        ws_base = ws_base.rstrip("/")
        if "/realtime" not in ws_base:
            ws_base = f"{ws_base}/v1/realtime"
        ws_url = f"{ws_base}?model={model}"
        logger.info(
            "Initializing Realtime session: group_id=%s model=%s base_url=%s voice=%s",
            session.group_id,
            model,
            ws_base,
            voice,
        )

        # Connect to provider Realtime API
        headers = {
            "Authorization": f"Bearer {api_key}",
            "OpenAI-Beta": "realtime=v1",
        }

        try:
            ws = await websockets.connect(ws_url, additional_headers=headers)
            session.oa_ws_connection = ws

            logger.info(
                f"Connected to Realtime API ({ws_base}) - group_id={session.group_id}"
            )

            # Configure the session. We intentionally omit:
            #   - ``turn_detection`` so the provider uses its own defaults.
            #   - ``input_audio_transcription`` — transcription is owned by
            #     our STT dispatch, triggered by the client once it receives
            #     the captured ``upload_id`` (attempt.chat.user_audio).
            session_config: dict[str, Any] = {
                "modalities": ["text", "audio"],
                "voice": voice,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
            }
            # Allow callers to opt back in explicitly if they ever need to.
            if kwargs.get("turn_detection") is not None:
                session_config["turn_detection"] = kwargs["turn_detection"]

            if instructions:
                session_config["instructions"] = instructions

            if tools:
                session_config["tools"] = self._format_tools(tools)
                session_config["tool_choice"] = "auto"

            # Diagnostic: what does the model actually see? Short form so
            # this doesn't flood logs — full payload is one JSON line.
            instr_preview = (
                (instructions or "")[:200].replace("\n", " ")
                + ("..." if instructions and len(instructions) > 200 else "")
            )
            tool_names = [
                t.get("name", "?") for t in session_config.get("tools") or []
            ]
            logger.info(
                f"session.update → group_id={session.group_id} "
                f"tools={tool_names} tool_choice={session_config.get('tool_choice')} "
                f"instructions_preview={instr_preview!r}"
            )

            # Send session.update to configure
            await ws.send(
                json.dumps(
                    {
                        "type": "session.update",
                        "session": session_config,
                    }
                )
            )

            # Start uplink and downlink loops
            uplink_task = asyncio.create_task(
                self._uplink_loop(session),
                name=f"uplink-{session.group_id}",
            )
            downlink_task = asyncio.create_task(
                self._downlink_loop(session),
                name=f"downlink-{session.group_id}",
            )

            self._tasks[session.group_id] = [uplink_task, downlink_task]

            logger.info(f"Started uplink/downlink loops - group_id={session.group_id}")

            return AudioSessionConfig(
                model=model,
                voice=voice,
                instructions=instructions,
                tools=tools,
                turn_detection=session_config.get("turn_detection"),
            )

        except Exception as e:
            logger.exception(f"Failed to connect to Realtime API: {e}")
            raise

    async def stop_session(self, session: AudioSession) -> None:
        """Stop the audio session and clean up resources.

        Cancels uplink/downlink tasks and closes the WebSocket connection.
        """
        group_id = session.group_id

        # Cancel tasks
        tasks = self._tasks.pop(group_id, [])
        for task in tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Close WebSocket
        ws = session.oa_ws_connection
        if ws:
            try:
                await ws.close()
            except Exception:
                pass
            session.oa_ws_connection = None

        logger.info(f"Stopped audio session - group_id={group_id}")

    async def _uplink_loop(self, session: AudioSession) -> None:
        """Consume from inbound_queue and send to OpenAI.

        Handles:
        - audio: Send PCM16 audio to OpenAI
        - mic.set_muted: Handle mute state changes
        """
        ws: ClientConnection = session.oa_ws_connection
        group_id = session.group_id

        # Periodic mic-input counter for diagnostics.
        _frames_since_log = 0
        _bytes_since_log = 0
        _last_log = asyncio.get_event_loop().time()

        # Debug tap — capture the first ~6s of uplink audio so we can
        # inspect whether the bytes are actually voice, silence, or the
        # wrong sample rate. Writes once per session. Guarded behind an
        # env var so it's off by default.
        import os
        _debug_tap_enabled = os.environ.get("GLOW_AUDIO_DEBUG_TAP") == "1"
        _debug_tap_bytes = bytearray()
        _debug_tap_limit = 24000 * 2 * 6  # 6s @ 24kHz mono s16le
        _debug_tap_path: str | None = None
        if _debug_tap_enabled:
            _debug_tap_path = f"uplink_debug_{group_id}.pcm"
            logger.info(
                f"Uplink debug tap ENABLED → will write first {_debug_tap_limit} "
                f"bytes to {_debug_tap_path}"
            )

        try:
            while True:
                # Get message from inbound queue
                msg = await session.inbound_queue.get()
                msg_type = msg.get("type")

                if msg_type == "audio":
                    # Send audio to OpenAI
                    audio_data = msg.get("pcm16_bytes")
                    if audio_data and not session.muted:
                        # Diagnostic counter — log ~every 2s how much audio
                        # is actually reaching the provider. 0 bytes/s while
                        # speaking means the mic path is broken upstream.
                        _frames_since_log += 1
                        raw_bytes_for_tap: bytes | None = None
                        if isinstance(audio_data, bytes):
                            _bytes_since_log += len(audio_data)
                            raw_bytes_for_tap = audio_data
                        else:
                            # base64 string — estimate decoded size
                            _bytes_since_log += (len(audio_data) * 3) // 4
                            try:
                                raw_bytes_for_tap = base64.b64decode(audio_data)
                            except Exception:
                                raw_bytes_for_tap = None

                        if (
                            _debug_tap_enabled
                            and _debug_tap_path is not None
                            and raw_bytes_for_tap
                            and len(_debug_tap_bytes) < _debug_tap_limit
                        ):
                            _debug_tap_bytes.extend(raw_bytes_for_tap)
                            if len(_debug_tap_bytes) >= _debug_tap_limit:
                                try:
                                    with open(_debug_tap_path, "wb") as f:
                                        f.write(bytes(_debug_tap_bytes))
                                    # Also compute simple RMS so silent input
                                    # is obvious from the log alone.
                                    import struct
                                    sample_count = len(_debug_tap_bytes) // 2
                                    samples = struct.unpack(
                                        f"<{sample_count}h",
                                        bytes(_debug_tap_bytes[: sample_count * 2]),
                                    )
                                    peak = max(abs(s) for s in samples) if samples else 0
                                    rms = (
                                        (sum(s * s for s in samples) / sample_count) ** 0.5
                                        if sample_count
                                        else 0
                                    )
                                    logger.info(
                                        f"Uplink debug tap wrote {_debug_tap_path} "
                                        f"({len(_debug_tap_bytes)} bytes). "
                                        f"peak={peak} rms={rms:.1f} "
                                        f"(silence≈peak<500, speech≈peak>3000)"
                                    )
                                except Exception as e:
                                    logger.warning(f"Debug tap write failed: {e}")
                        _now = asyncio.get_event_loop().time()
                        if _now - _last_log >= 2.0:
                            rate_kbps = (_bytes_since_log * 8) / (1000 * (_now - _last_log))
                            logger.info(
                                f"Uplink audio: {_frames_since_log} frames / "
                                f"{_bytes_since_log} bytes in last "
                                f"{_now - _last_log:.1f}s "
                                f"({rate_kbps:.1f} kbps) - group_id={group_id}"
                            )
                            _frames_since_log = 0
                            _bytes_since_log = 0
                            _last_log = _now
                        # Buffer raw PCM16 bytes for saving user speech
                        if session.speech_buffering:
                            raw_bytes = (
                                audio_data
                                if isinstance(audio_data, bytes)
                                else base64.b64decode(audio_data)
                            )
                            session.speech_audio_buffer.extend(raw_bytes)

                        # Convert to base64 if bytes
                        if isinstance(audio_data, bytes):
                            audio_b64 = base64.b64encode(audio_data).decode("utf-8")
                        else:
                            # Already base64 string
                            audio_b64 = audio_data

                        await ws.send(
                            json.dumps(
                                {
                                    "type": "input_audio_buffer.append",
                                    "audio": audio_b64,
                                }
                            )
                        )

                elif msg_type == "mic.set_muted":
                    session.muted = msg.get("muted", False)
                    logger.debug(f"Mic muted={session.muted} - group_id={group_id}")

                    # If unmuting, clear the buffer to start fresh
                    if not session.muted:
                        await ws.send(
                            json.dumps(
                                {
                                    "type": "input_audio_buffer.clear",
                                }
                            )
                        )

        except asyncio.CancelledError:
            logger.info(f"Uplink loop cancelled - group_id={group_id}")
            raise
        except Exception as e:
            logger.exception(f"Uplink loop error - group_id={group_id}: {e}")
            await self._emitter.on_error(group_id, f"Uplink error: {str(e)}")

    async def _downlink_loop(self, session: AudioSession) -> None:
        """Receive from provider and call emitter callbacks.

        Translates provider Realtime events to emitter callback calls.
        """
        ws: ClientConnection = session.oa_ws_connection
        group_id = session.group_id

        # Track current item for user speech
        current_user_item_id: str | None = None

        logger.info(f"Downlink loop entered — waiting for first provider message — group_id={group_id}")
        _first_message_logged = False

        try:
            async for message in ws:
                if not _first_message_logged:
                    preview = message if isinstance(message, str) else f"<{len(message)} bytes>"
                    logger.info(
                        f"Downlink first message — group_id={group_id} "
                        f"preview={preview[:500] if isinstance(preview, str) else preview}"
                    )
                    _first_message_logged = True

                # LiteLLM proxy re-frames OpenAI text events as binary — json
                # accepts either, so parse without branching on frame type.
                event = json.loads(message)
                event_type = event.get("type", "")

                # Log events for debugging (except frequent audio/transcript deltas)
                if event_type not in (
                    "response.audio.delta",
                    "response.audio_transcript.delta",
                ):
                    logger.info(f"Provider event: {event_type} - group_id={group_id}")

                # -- Session lifecycle --

                if event_type == "session.created":
                    logger.info(f"Session created - group_id={group_id}")

                elif event_type == "session.updated":
                    logger.info(f"Session updated - group_id={group_id}")

                # -- User speech --

                elif event_type == "input_audio_buffer.speech_started":
                    item_id = event.get("item_id", f"user-{group_id}")
                    current_user_item_id = item_id
                    # Start buffering user audio frames
                    session.speech_audio_buffer = bytearray()
                    session.speech_buffering = True
                    await self._emitter.on_user_speech_start(group_id, item_id)

                elif event_type == "input_audio_buffer.speech_stopped":
                    # User turn over. Persist the captured PCM via the
                    # canonical audio upload chain and emit audios_id.
                    session.speech_buffering = False
                    speech_audio = bytes(session.speech_audio_buffer)
                    session.speech_audio_buffer = bytearray()
                    if speech_audio:
                        try:
                            # 24kHz mono PCM16 → bytes / 2 / 24000 seconds
                            duration_ms = int(
                                (len(speech_audio) / 2) * 1000 / 24000
                            )
                            audios_id = await _persist_realtime_audio(
                                session=session,
                                pcm_bytes=speech_audio,
                                duration_ms=duration_ms,
                                side="user",
                            )
                            await self._emitter.on_user_audio(
                                group_id,
                                audios_id=str(audios_id),
                                duration_ms=duration_ms,
                            )
                        except Exception as exc:
                            logger.exception(
                                f"Failed to persist user speech audio: {exc}"
                            )

                # -- Assistant output items --

                elif event_type == "response.output_item.added":
                    item = event.get("item", {})
                    item_id = item.get("id", "")
                    item_type = item.get("type", "")
                    if item_type == "message":
                        await self._emitter.on_audio_start(group_id)
                        await self._emitter.on_transcript_start(group_id, item_id)
                    elif item_type == "function_call":
                        call_id = item.get("call_id", "")
                        name = item.get("name", "")
                        await self._emitter.on_tool_call_start(
                            group_id, item_id, call_id, name
                        )

                # -- Assistant audio --

                elif event_type == "response.audio.delta":
                    audio_b64 = event.get("delta", "")
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                        # Always accumulate assistant audio; flushed to the
                        # canonical audio upload chain on response.audio.done
                        # and emitted as attempt.chat.assistant_audio.
                        session.assistant_audio_buffer.extend(audio_bytes)
                        await self._emitter.on_audio_delta(group_id, audio_bytes)

                # -- Assistant transcript --

                elif event_type == "response.audio_transcript.delta":
                    transcript = event.get("delta", "")
                    if transcript:
                        await self._emitter.on_transcript_delta(group_id, transcript)

                elif event_type == "response.audio_transcript.done":
                    item_id = event.get("item_id", "")
                    transcript = event.get("transcript", "")
                    await self._emitter.on_transcript_complete(
                        group_id, item_id, transcript
                    )

                # -- Tool calls --

                elif event_type == "response.function_call_arguments.delta":
                    call_id = event.get("call_id", "")
                    delta = event.get("delta", "")
                    if delta:
                        await self._emitter.on_tool_call_delta(group_id, call_id, delta)

                elif event_type == "response.function_call_arguments.done":
                    call_id = event.get("call_id", "")
                    name = event.get("name", "")
                    arguments = event.get("arguments", "")
                    await self._emitter.on_tool_call_complete(
                        group_id, call_id, name, arguments
                    )
                    # Close the tool-execution loop: run the tool, feed the
                    # result back to the provider as a ``function_call_output``
                    # and prompt the model to continue with ``response.create``.
                    # Without this the model waits for an output it will
                    # never receive and the turn ends silently.
                    await self._execute_tool_and_respond(
                        session=session,
                        call_id=call_id,
                        tool_name=name,
                        arguments=arguments,
                    )

                # -- Audio complete --

                elif event_type == "response.audio.done":
                    # Flush the accumulated assistant PCM through the
                    # canonical audio upload chain and emit the resulting
                    # audios_id so the client can attach it to a chat
                    # message without any promotion step.
                    assistant_pcm = bytes(session.assistant_audio_buffer)
                    session.assistant_audio_buffer = bytearray()
                    if assistant_pcm:
                        try:
                            duration_ms = int(
                                (len(assistant_pcm) / 2) * 1000 / 24000
                            )
                            assistant_audios_id = await _persist_realtime_audio(
                                session=session,
                                pcm_bytes=assistant_pcm,
                                duration_ms=duration_ms,
                                side="assistant",
                            )
                            await self._emitter.on_assistant_audio(
                                group_id,
                                audios_id=str(assistant_audios_id),
                                duration_ms=duration_ms,
                            )
                        except Exception as exc:
                            logger.exception(
                                f"Failed to persist assistant audio: {exc}"
                            )
                    await self._emitter.on_audio_complete(group_id)

                # -- Response lifecycle --

                elif event_type == "response.done":
                    response = event.get("response", {})
                    usage = response.get("usage", {})
                    status = response.get("status", "completed")
                    logger.info(
                        f"Response done - group_id={group_id}, "
                        f"status={status}, usage={usage}"
                    )
                    if status == "cancelled":
                        await self._emitter.on_response_cancelled(group_id, usage)
                    else:
                        await self._emitter.on_response_done(group_id, usage)

                elif event_type == "error":
                    error = event.get("error", {})
                    error_msg = error.get("message", "Unknown error")
                    logger.error(f"Provider error - group_id={group_id}: {error_msg}")
                    await self._emitter.on_error(group_id, error_msg)

        except asyncio.CancelledError:
            logger.info(f"Downlink loop cancelled - group_id={group_id}")
            raise
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"WebSocket closed - group_id={group_id}: {e}")
        except Exception as e:
            logger.exception(f"Downlink loop error - group_id={group_id}: {e}")
            await self._emitter.on_error(group_id, f"Downlink error: {str(e)}")

    async def _execute_tool_and_respond(
        self,
        *,
        session: AudioSession,
        call_id: str,
        tool_name: str,
        arguments: str,
    ) -> None:
        """Execute the tool the realtime model asked for and continue the turn.

        Mirrors the text agentic loop in ``app.infra.generation.execute
        ._execute_agent_dispatch``: parse args, ``resolve_tool_spec``, run
        ``execute_infra_operation`` with an ``InfraContext`` built from the
        ``AudioSession`` identity, then write a ``conversation.item.create``
        carrying the ``function_call_output`` plus a ``response.create`` so
        the model can actually speak the follow-up turn (without the
        second message the provider sits idle waiting for a response).
        """
        ws: ClientConnection | None = session.oa_ws_connection
        if ws is None:
            logger.warning(
                f"No WS on session — cannot feed tool result back "
                f"(group_id={session.group_id})"
            )
            return

        # Lazy imports keep the adapter free of business-logic deps at load.
        from app.infra.tools.execute_infra_operation import (
            InfraContext,
            execute_infra_operation,
        )
        from app.infra.tools.resolve_tool_spec import resolve_tool_spec

        # 1. Parse the JSON args the model streamed.
        try:
            arguments_dict = json.loads(arguments) if arguments else {}
        except json.JSONDecodeError:
            arguments_dict = {}

        # 2. Look up the tool def. Keys are sanitized names, matching what
        #    the provider sees in session.update.tools.
        tool_def = session.tool_def_by_name.get(tool_name)

        if not tool_def:
            tool_result_str = json.dumps(
                {
                    "success": False,
                    "message": f"Tool not found: {tool_name}",
                    "error_stage": "tool_resolve",
                }
            )
        else:
            try:
                spec = resolve_tool_spec(tool_def, arguments_dict)
                # ``session.run_id`` rotates per turn via
                # ``rotate_run_id`` in run_complete_impl — those rotated UUIDs
                # don't have a matching ``runs_entry`` row, which would
                # FK-violate ``calls_entry.run_id -> runs_entry.id`` in the
                # audit layer. Leave run_id unset for realtime-originated
                # tool calls; we lose the per-turn run correlation but keep
                # the tool execution working.
                ctx = InfraContext(
                    pool=get_pool(),
                    redis=get_redis_client(),
                    profile_id=UUID(session.profile_id)
                    if session.profile_id
                    else UUID(int=0),
                    session_id=UUID(session.session_id)
                    if session.session_id
                    else None,
                    group_id=UUID(session.group_id)
                    if session.group_id
                    else None,
                    run_id=None,
                    sid=session.sid,
                    soft=True,
                    operation_key=uuid_mod.uuid4(),
                    instruction_template=tool_def.get("_instruction_template"),
                )
                results = await execute_infra_operation(ctx, spec)
                tool_result_str = json.dumps(
                    {
                        "success": all(r.success for r in results),
                        "results": [r.model_dump(mode="json") for r in results],
                    }
                )
                logger.info(
                    f"Realtime tool result: name={tool_name} "
                    f"success={all(r.success for r in results)} "
                    f"preview={tool_result_str[:500]}"
                )
            except Exception as exc:
                logger.exception(
                    f"Realtime tool execution failed: tool={tool_name} "
                    f"group_id={session.group_id}"
                )
                tool_result_str = json.dumps(
                    {"success": False, "message": str(exc)}
                )

        # 3. Feed the result back to the provider as function_call_output.
        try:
            await ws.send(
                json.dumps(
                    {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": tool_result_str,
                        },
                    }
                )
            )
            # 4. Ask the model for the next turn. ``modalities`` is set so
            #    the continuation can be spoken (the session.update already
            #    allows both, but response.create scopes per-response).
            await ws.send(
                json.dumps(
                    {
                        "type": "response.create",
                        "response": {"modalities": ["text", "audio"]},
                    }
                )
            )
        except Exception as exc:
            logger.exception(
                f"Failed to send function_call_output/response.create "
                f"back to provider: group_id={session.group_id} err={exc}"
            )

    def _format_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Format tools for OpenAI Realtime API.

        Realtime accepts exactly ``{type, name, description, parameters}``.
        Glow's internal tool dicts carry many extra fields (id, args,
        args_outputs, resources, entries, artifacts, operation, ...) which
        the provider rejects as schema errors, so we strip to the 4
        whitelisted keys here.
        """
        from app.infra.artifacts.convert_tools_to_openai_format import sanitize_tool_name

        formatted: list[dict[str, Any]] = []
        for tool in tools or []:
            if not isinstance(tool, dict):
                continue
            if "function" in tool and isinstance(tool["function"], dict):
                func = tool["function"]
                name = func.get("name")
                description = func.get("description")
                parameters = func.get("parameters") or {"type": "object", "properties": {}}
            else:
                name = tool.get("name")
                description = tool.get("description")
                parameters = tool.get("parameters") or {"type": "object", "properties": {}}
            if not name:
                continue
            formatted.append(
                {
                    "type": "function",
                    "name": sanitize_tool_name(name),
                    "description": description or "",
                    "parameters": parameters,
                }
            )
        return formatted
