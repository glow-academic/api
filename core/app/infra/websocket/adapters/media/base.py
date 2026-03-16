"""Base media adapter interface for image/video generation."""

from abc import ABC, abstractmethod
from typing import Any, Protocol

from pydantic import BaseModel


class MediaResult(BaseModel):
    """Result of a media generation operation."""

    file_path: str
    mime_type: str
    file_size: int
    upload_id: str


class MediaEventEmitter(Protocol):
    """Callback protocol for media adapter events.

    Adapters call these methods instead of importing socket emit functions
    directly, keeping the infra layer decoupled from the socket layer.
    """

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
        ...

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
        ...

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
        result: "MediaResult",
        metadata: dict[str, Any] | None,
    ) -> None:
        """Media generation completed successfully."""
        ...

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
        ...


class BaseMediaAdapter(ABC):
    """Base class for media (image/video) adapters.

    Media adapters handle one-shot generation: given a prompt, they produce
    a file (image or video) and return a MediaResult with the saved path
    and upload record ID.
    """

    def __init__(self, emitter: MediaEventEmitter) -> None:
        self._emitter = emitter

    @abstractmethod
    async def generate(
        self,
        modality: str,
        prompt: str,
        model: str,
        api_key: str,
        *,
        base_url: str | None = None,
        quality: str | None = None,
        extra_body: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> MediaResult:
        """Generate an image or video from a prompt.

        Args:
            modality: "image" or "video"
            prompt: The generation prompt
            model: Model name (e.g. "dall-e-3", "sora")
            api_key: Decrypted API key
            base_url: Provider endpoint override
            quality: Quality setting (e.g. "hd")
            extra_body: Additional provider-specific parameters
            context: Dict with sid/run_id/group_id/artifact_type/resource_type/
                     resource_id/metadata for emitting progress events

        Returns:
            MediaResult with file_path, mime_type, file_size, upload_id
        """
        pass
