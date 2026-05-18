"""Standalone smoke test for the LiteLLM realtime endpoint.

Bypasses the Glow pipeline entirely — connects directly to the proxy's
``/v1/realtime`` WebSocket, sends a ``session.update`` matching what the
server does, then pushes a ``response.create`` to make the model speak
without needing mic input. Every event the provider sends is printed;
audio deltas are accumulated and written to ``smoke_realtime_output.pcm``.

Usage::

    uv run python core/scripts/smoke_realtime.py \
        --base ws://localhost:4000/v1/realtime \
        --model glow-realtime \
        --api-key "$OPENAI_API_KEY"

If ``--api-key`` is omitted, reads from the ``OPENAI_API_KEY`` env var.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any

import websockets  # type: ignore


_SMOKE_TOOL_ATTEMPT_GET = {
    "type": "function",
    "name": "Attempt_Get",
    "description": "Fetch the current attempt context — personas, rubric, messages.",
    "parameters": {
        "type": "object",
        "properties": {
            "attempt_id": {"type": "string", "description": "UUID of the attempt"},
        },
        "required": ["attempt_id"],
        "additionalProperties": False,
    },
}

_SMOKE_TOOL_CHAT_MESSAGE = {
    "type": "function",
    "name": "Attempt_Chat_Message",
    "description": "Record a persona's response in the ongoing chat.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string"},
            "persona_id": {"type": "string"},
            "text": {"type": "string"},
        },
        "required": ["chat_id", "persona_id", "text"],
        "additionalProperties": False,
    },
}


async def run(
    base_url: str,
    model: str,
    api_key: str,
    voice: str,
    prompt: str,
    *,
    with_tools: bool = False,
) -> None:
    url = f"{base_url.rstrip('/')}?model={model}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "OpenAI-Beta": "realtime=v1",
    }

    print(f"→ connecting: {url}")
    print(f"  voice={voice}  prompt={prompt!r}")

    try:
        ws = await websockets.connect(url, additional_headers=headers)
    except Exception as exc:  # pragma: no cover — diagnostic script
        print(f"!! connect failed: {exc}")
        sys.exit(2)

    print("✓ connected")

    # Mirror what the Glow adapter sends (adapters/audio/realtime.py).
    # ``turn_detection`` is deliberately omitted so the provider picks
    # its own defaults — our tuned thresholds were causing VAD to miss
    # normal speech in the pipeline.
    session: dict[str, Any] = {
        "modalities": ["text", "audio"],
        "voice": voice,
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "input_audio_transcription": {"model": "whisper-1"},
    }
    if with_tools:
        session["tools"] = [_SMOKE_TOOL_ATTEMPT_GET, _SMOKE_TOOL_CHAT_MESSAGE]
        session["tool_choice"] = "auto"
        print(f"  declaring {len(session['tools'])} tools on session.update")
    await ws.send(json.dumps({"type": "session.update", "session": session}))
    print("→ session.update sent")

    # Force the model to respond immediately — no mic input needed. When
    # tools are declared the prompt asks the model to call one so we can
    # verify the tool-declaration shape is accepted end-to-end.
    response_instructions = (
        "Call Attempt_Chat_Message with chat_id='chat-1', persona_id='p-1', "
        "and a short in-character text. Do not just speak."
        if with_tools
        else prompt
    )
    await ws.send(
        json.dumps(
            {
                "type": "response.create",
                "response": {
                    "modalities": ["text", "audio"],
                    "instructions": response_instructions,
                },
            }
        )
    )
    print("→ response.create sent")

    audio_path = Path("smoke_realtime_output.pcm")
    audio_bytes = bytearray()
    event_counts: dict[str, int] = {}
    transcript_chunks: list[str] = []

    try:
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=30.0)
            evt = json.loads(raw)
            et = evt.get("type", "?")
            event_counts[et] = event_counts.get(et, 0) + 1

            if et == "response.audio.delta":
                audio_bytes.extend(base64.b64decode(evt.get("delta", "")))
            elif et == "response.audio_transcript.delta":
                transcript_chunks.append(evt.get("delta", ""))
            elif et == "response.audio_transcript.done":
                print(f"  transcript: {evt.get('transcript', '')!r}")
            elif et == "response.function_call_arguments.done":
                print(
                    f"  tool_call: name={evt.get('name')!r} "
                    f"call_id={evt.get('call_id')!r} "
                    f"args={evt.get('arguments')!r}"
                )
            elif et == "error":
                print(f"!! error event: {evt.get('error')}")
            elif et == "response.done":
                print("← response.done")
                break
            elif et in ("session.created", "session.updated"):
                print(f"  {et}")
    except asyncio.TimeoutError:
        print("!! timed out waiting for response.done")
    finally:
        await ws.close()

    audio_path.write_bytes(bytes(audio_bytes))
    print()
    print(f"  wrote {len(audio_bytes)} bytes of pcm16 → {audio_path}")
    print(f"  event counts: {event_counts}")
    if transcript_chunks:
        print(f"  full transcript: {''.join(transcript_chunks)!r}")
    print()
    print("Play the audio:")
    print(
        f"  ffplay -f s16le -ar 24000 -ac 1 {audio_path}  "
        "(or import into Audacity: Raw, 24kHz mono s16le)"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="ws://localhost:4000/v1/realtime")
    parser.add_argument("--model", default="glow-realtime")
    parser.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", "sk-none"))
    parser.add_argument("--voice", default="alloy")
    parser.add_argument(
        "--prompt",
        default="Say hello in one short sentence so I can confirm the pipeline works.",
    )
    parser.add_argument(
        "--with-tools",
        action="store_true",
        help="Declare two sample tools on session.update and ask the model to call one.",
    )
    args = parser.parse_args()
    asyncio.run(
        run(
            args.base,
            args.model,
            args.api_key,
            args.voice,
            args.prompt,
            with_tools=args.with_tools,
        )
    )


if __name__ == "__main__":
    main()
