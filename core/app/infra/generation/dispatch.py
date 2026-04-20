"""Pair-based modality dispatch rule used by execute_generation.

Takes (input_modalities, output_modalities) and returns a string tag that
names the executor. Kept as pure Python so tests can exercise the rule
without any I/O.

Executors:
  "realtime"     → live audio session (bidirectional, tool-use enabled)
  "agentic_text" → streaming text loop (tool-use enabled — "call" required)
  "tts"          → text → audio (one-shot via /audio/speech)
  "stt"          → audio → text (one-shot via /audio/transcriptions)
  "image"        → text → image
  "video"        → text → video
  "unsupported"  → no matching rule
"""

from __future__ import annotations


HEAVY_OUT = {"audio", "image", "video"}


def resolve_executor(
    input_modalities: set[str],
    output_modalities: set[str],
) -> str:
    """Pick an executor tag for a given (input, output) modality pair."""
    ins = input_modalities or set()
    outs = output_modalities or set()

    # Realtime: any live-audio input plus audio output. Call is implicit —
    # tool use is always on during a realtime session.
    if "audio_stream" in ins and "audio" in outs:
        return "realtime"

    # Agentic text loop: text-only input, text output (possibly with call).
    # No heavy-out modalities and no audio streaming in.
    if ins == {"text"} and "text" in outs and not (outs & HEAVY_OUT):
        return "agentic_text"

    # TTS: text in, audio out only (no text/call — those demand the loop).
    if ins == {"text"} and outs == {"audio"}:
        return "tts"

    # STT: one-shot audio in, text out only.
    if ins == {"audio"} and outs == {"text"}:
        return "stt"

    # Image/video gen: text in, single heavy-out modality.
    if ins == {"text"} and outs == {"image"}:
        return "image"
    if ins == {"text"} and outs == {"video"}:
        return "video"

    return "unsupported"


__all__ = ["resolve_executor"]
