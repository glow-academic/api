"""Media generation event contract — canonical ``{artifact}.generate.{image|video}.*`` emits.

Provides ``InternalBusMediaEmitter`` (the concrete ``MediaEventEmitter``
used by ``LitellmMediaAdapter``) and ``get_media_emitter`` for the
adapter singleton. Keeps the adapter layer decoupled from socket.io —
the adapter only knows the protocol.
"""

from typing import Any

from app.infra.generation.emit import canonical_generation_event
from app.infra.globals import get_internal_sio
from app.infra.websocket.adapters.media.base import MediaResult


def _media_event_name(
    modality: str, phase: str, artifact_type: str | None,
) -> str:
    """Canonical per-artifact name, falling back to ``generate_error`` when
    ``artifact_type`` is missing (shouldn't happen — every dispatch carries
    it — but keeps the emit path non-crashing).
    """
    if artifact_type:
        return canonical_generation_event(artifact_type, modality, phase)
    return "generate_error"


class InternalBusMediaEmitter:
    """Concrete MediaEventEmitter that emits via the internal event bus.

    Satisfies the MediaEventEmitter protocol defined in
    app.infra.websocket.adapters.media.base.
    """

    def __init__(self) -> None:
        self._bus = get_internal_sio()

    async def on_start(
        self,
        modality: str,
        *,
        sid: str,
        run_id: str,
        group_id: str | None,
        artifact_type: str | None,
        resource_type: str | None,
        resource_id: str | None,
        metadata: dict[str, Any] | None,
    ) -> None:
        """Media generation started."""
        await self._bus.emit(
            _media_event_name(modality, "start", artifact_type),
            {
                "modality": modality,
                "sid": sid,
                "run_id": run_id,
                "group_id": group_id,
                "artifact_type": artifact_type,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "type": "start",
                "message": f"{modality.capitalize()} generation started",
                "metadata": metadata,
            },
        )

    async def on_progress(
        self,
        modality: str,
        *,
        sid: str,
        run_id: str,
        group_id: str | None,
        artifact_type: str | None,
        resource_type: str | None,
        resource_id: str | None,
        message: str,
        metadata: dict[str, Any] | None,
    ) -> None:
        """Media generation progress update."""
        await self._bus.emit(
            _media_event_name(modality, "progress", artifact_type),
            {
                "modality": modality,
                "sid": sid,
                "run_id": run_id,
                "group_id": group_id,
                "artifact_type": artifact_type,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "type": "progress",
                "message": message,
                "metadata": metadata,
            },
        )

    async def on_complete(
        self,
        modality: str,
        *,
        sid: str,
        run_id: str,
        group_id: str | None,
        artifact_type: str | None,
        resource_type: str | None,
        resource_id: str | None,
        result: MediaResult,
        metadata: dict[str, Any] | None,
    ) -> None:
        """Media generation completed successfully."""
        await self._bus.emit(
            _media_event_name(modality, "complete", artifact_type),
            {
                "modality": modality,
                "sid": sid,
                "run_id": run_id,
                "group_id": group_id,
                "artifact_type": artifact_type,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "type": "complete",
                "event_type": "media_complete",
                "file_path": result.file_path,
                "mime_type": result.mime_type,
                "file_size": result.file_size,
                "upload_id": result.upload_id,
                "images_id": result.images_id,
                "videos_id": result.videos_id,
                "metadata": metadata,
            },
        )

    async def on_error(
        self,
        modality: str,
        *,
        sid: str,
        run_id: str,
        group_id: str | None,
        artifact_type: str | None,
        resource_type: str | None,
        resource_id: str | None,
        error_message: str,
        metadata: dict[str, Any] | None,
    ) -> None:
        """Media generation failed."""
        await self._bus.emit(
            _media_event_name(modality, "error", artifact_type),
            {
                "modality": modality,
                "sid": sid,
                "run_id": run_id,
                "group_id": group_id,
                "artifact_type": artifact_type,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "type": "error",
                "error_message": error_message,
                "metadata": metadata,
            },
        )


def get_media_emitter() -> InternalBusMediaEmitter:
    """Factory for the media event emitter singleton."""
    return InternalBusMediaEmitter()
