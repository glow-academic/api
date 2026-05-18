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
    """Canonical per-artifact name. ``artifact_type`` should always be set;
    if it isn't, use ``unknown.generate.<modality>.<phase>`` so the emit
    doesn't crash — no registered handler will pick it up, but it's logged
    at the dispatch level as an upstream bug.
    """
    return canonical_generation_event(artifact_type or "unknown", modality, phase)


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
        message_id: str | None = None,
        profile_id: str | None = None,
    ) -> None:
        """Media generation started. ``message_id`` is the pre-minted
        ``messages_entry.id`` the produced asset will be attributed to —
        FE listeners use it as the React key for the optimistic skeleton
        bubble so ``on_complete`` can swap content in place."""
        await self._bus.emit(
            _media_event_name(modality, "start", artifact_type),
            {
                "modality": modality,
                "sid": sid,
                # ``rooms=[profile_id]`` matches the text-emit pattern in
                # ``execute.py`` so every observer for this user
                # (additional tabs, the make-debug panel, …) sees media
                # events too. Without it, ``_generic_forward`` falls
                # back to ``[sid]`` and the emit reaches only the
                # originating page.
                "rooms": [profile_id] if profile_id else [],
                "run_id": run_id,
                "group_id": group_id,
                "artifact_type": artifact_type,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "message_id": message_id,
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
        message_id: str | None = None,
        profile_id: str | None = None,
    ) -> None:
        """Media generation progress update."""
        await self._bus.emit(
            _media_event_name(modality, "progress", artifact_type),
            {
                "modality": modality,
                "sid": sid,
                "rooms": [profile_id] if profile_id else [],
                "run_id": run_id,
                "group_id": group_id,
                "artifact_type": artifact_type,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "message_id": message_id,
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
        profile_id: str | None = None,
    ) -> None:
        """Media generation completed successfully. ``result.message_id``
        (when present) carries the ``messages_entry.id`` the upload was
        attributed to — same id as the matching ``on_start`` emit so the
        FE listener can locate its optimistic skeleton and swap content
        in place."""
        await self._bus.emit(
            _media_event_name(modality, "complete", artifact_type),
            {
                "modality": modality,
                "sid": sid,
                "rooms": [profile_id] if profile_id else [],
                "run_id": run_id,
                "group_id": group_id,
                "artifact_type": artifact_type,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "message_id": result.message_id,
                "type": "complete",
                "event_type": "media_complete",
                "file_path": result.file_path,
                "mime_type": result.mime_type,
                "file_size": result.file_size,
                "upload_id": result.upload_id,
                "images_id": result.images_id,
                "videos_id": result.videos_id,
                "audios_id": result.audios_id,
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
        message_id: str | None = None,
        profile_id: str | None = None,
    ) -> None:
        """Media generation failed."""
        await self._bus.emit(
            _media_event_name(modality, "error", artifact_type),
            {
                "modality": modality,
                "sid": sid,
                "rooms": [profile_id] if profile_id else [],
                "run_id": run_id,
                "group_id": group_id,
                "artifact_type": artifact_type,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "message_id": message_id,
                "type": "error",
                "error_message": error_message,
                "metadata": metadata,
            },
        )


def get_media_emitter() -> InternalBusMediaEmitter:
    """Factory for the media event emitter singleton."""
    return InternalBusMediaEmitter()
