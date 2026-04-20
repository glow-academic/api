"""Shared modality event emission helpers.

Used by every generation executor (text, audio, image, video, tts, stt) so
event naming stays consistent across the pipeline.

Events are emitted on the internal bus using the canonical artifact-scoped
name: ``{artifact_type}.generate.{modality}.{phase}``. Forwarders under
``app/ws/output/attempt/generate/*`` (etc.) translate to client sockets.

Callers must supply ``artifact_type`` (or include it in the payload). If it
is missing we fall back to ``generate_error`` — the only remaining non-
artifact-scoped name, carved out as a pre-dispatch error channel.
"""

from __future__ import annotations

from typing import Any

from app.infra.websocket.socket_event import EmitFn, internal_event

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

    Canonical only — no legacy ``generate_{modality}_{phase}`` twin. When
    the modality is unsupported, falls back to ``generate_error`` (the
    pre-dispatch error channel); if ``artifact_type`` is also known, the
    artifact-scoped ``{artifact}.generate.error`` is fired alongside.
    """
    effective_artifact = artifact_type or (
        payload.get("artifact_type") if isinstance(payload, dict) else None
    )
    if modality not in _SUPPORTED_MODALITIES:
        events = [internal_event("generate_error", payload)]
        if effective_artifact:
            events.append(
                internal_event(
                    canonical_generation_event(effective_artifact, "error"),
                    payload,
                )
            )
        await emit(events)
        return

    if not effective_artifact:
        # No artifact_type → nothing to scope the canonical name to. Flag
        # on the error channel so the call isn't invisible.
        await emit(
            [
                internal_event(
                    "generate_error",
                    {
                        **payload,
                        "error_message": (
                            "emit_modality_event called without artifact_type "
                            f"(modality={modality}, phase={phase})"
                        ),
                    },
                )
            ]
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
