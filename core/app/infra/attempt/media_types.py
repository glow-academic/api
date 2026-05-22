"""Types for attempt media operations (upload + download)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

# ── Audio ─────────────────────────────────────────────────────────────────────

class AudioUploadAttemptApiResponse(BaseModel):
    """Response model for attempt audio upload endpoint."""

    audio_id: UUID = Field(..., description="UUID of the audios_entry (server plumbing; public handle is audios_id)")
    audios_id: UUID = Field(..., description="UUID of the audios_resource — use this for /generate, /chat/message, download")
    upload_id: UUID = Field(..., description="UUID of the uploads_entry (primitive raw file)")
    idempotency_key: UUID | None = Field(None, description="Server-minted soft-call key; echo with accept to promote/reject the staged upload.")


class AudioDownloadAttemptApiRequest(BaseModel):
    """Request model for attempt audio download endpoint."""

    audio_id: UUID = Field(..., description="UUID of the audios_entry to download")


class AudioDownloadAttemptApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


# ── Image ─────────────────────────────────────────────────────────────────────

class ImageDownloadAttemptApiRequest(BaseModel):
    """Request model for attempt image download endpoint."""

    image_id: UUID = Field(..., description="UUID of the images_resource to download")


class ImageDownloadAttemptApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


# ── Video ─────────────────────────────────────────────────────────────────────

class VideoDownloadAttemptApiRequest(BaseModel):
    """Request model for attempt video download endpoint."""

    video_id: UUID = Field(..., description="UUID of the videos_entry to download")


class VideoDownloadAttemptApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


# ── Text ──────────────────────────────────────────────────────────────────────

class TextDownloadAttemptApiRequest(BaseModel):
    """Request model for attempt text download endpoint."""

    text_id: UUID = Field(..., description="UUID of the texts_entry to download")


class TextDownloadAttemptApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


# ── File ──────────────────────────────────────────────────────────────────────

class FileDownloadAttemptApiRequest(BaseModel):
    """Request model for attempt file download endpoint."""

    file_id: UUID = Field(..., description="UUID of the files_entry to download")


class FileDownloadAttemptApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


class FilePreviewAttemptApiRequest(BaseModel):
    """Request model for attempt file preview endpoint."""

    file_id: UUID = Field(..., description="UUID of the files_entry to preview")
