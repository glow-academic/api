"""Media generation event contract — all generate_image_*/generate_video_* events.

This module provides:
1. InternalBusMediaEmitter — concrete MediaEventEmitter that wraps internal_sio.emit()
2. get_media_emitter() — factory for use by the media adapter singleton

The adapter (litellm.py) receives a MediaEventEmitter via its constructor,
keeping the infra layer decoupled from the socket layer.
"""

from typing import Any

from app.infra.globals import get_internal_sio
from app.infra.websocket.adapters.media.base import MediaResult


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
            f"generate_{modality}_start",
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
            f"generate_{modality}_progress",
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
            f"generate_{modality}_complete",
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
            f"generate_{modality}_error",
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
