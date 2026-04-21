"""Shared modality event emission helpers.

Used by every generation executor (text, audio, image, video, tts, stt) so
event naming stays consistent across the pipeline.

Events are emitted on the internal bus using the canonical artifact-scoped
name: ``{artifact_type}.generate.{modality}.{phase}``. Forwarders under
``app/ws/output/attempt/generate/*`` (etc.) translate to client sockets.

Callers must supply ``artifact_type`` (or include it in the payload).
Missing ``artifact_type`` or an unsupported modality is a programmer
error — logged and swallowed, nothing emitted.
"""

from __future__ import annotations

import logging
from typing import Any

from app.infra.websocket.socket_event import EmitFn, internal_event

logger = logging.getLogger(__name__)

_SUPPORTED_MODALITIES = {"text", "audio", "image", "video", "call"}


def canonical_generation_event(
    artifact_type: str, sub: str, phase: str | None = None,
) -> str:
    """Return the canonical artifact-scoped event name.

    ``{artifact}.generate.{sub}`` when ``phase`` is None, else
    ``{artifact}.generate.{sub}.{phase}``.
    """
    if phase:
        return f"{artifact_type}.generate.{sub}.{phase}"
    return f"{artifact_type}.generate.{sub}"


async def emit_modality_event(
    emit: EmitFn,
    modality: str,
    phase: str,
    payload: dict[str, Any],
    *,
    artifact_type: str | None = None,
) -> None:
    """Emit a modality-scoped generation event on the internal bus.

    Canonical only — event name is always
    ``{artifact}.generate.{modality}.{phase}``. Missing artifact_type or an
    unsupported modality is a programmer error; logged and swallowed so an
    upstream bug can't crash the pipeline.
    """
    effective_artifact = artifact_type or (
        payload.get("artifact_type") if isinstance(payload, dict) else None
    )
    if modality not in _SUPPORTED_MODALITIES:
        logger.error(
            f"emit_modality_event: unsupported modality={modality} phase={phase} "
            f"artifact_type={effective_artifact}"
        )
        if effective_artifact:
            await emit(
                [
                    internal_event(
                        canonical_generation_event(effective_artifact, "error"),
                        payload,
                    )
                ]
            )
        return

    if not effective_artifact:
        logger.error(
            f"emit_modality_event called without artifact_type "
            f"(modality={modality}, phase={phase})"
        )
        return

    await emit(
        [
            internal_event(
                canonical_generation_event(effective_artifact, modality, phase),
                payload,
            )
        ]
    )


async def emit_canonical_event(
    emit: EmitFn,
    artifact_type: str,
    sub: str,
    phase: str | None,
    payload: dict[str, Any],
) -> None:
    """Emit a single canonical artifact-scoped event."""
    await emit(
        [
            internal_event(
                canonical_generation_event(artifact_type, sub, phase), payload
            )
        ]
    )
