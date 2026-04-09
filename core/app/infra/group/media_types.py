"""Group media types — request/result models for all download operations."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# Image Download
# =============================================================================


class ImageDownloadGroupApiRequest(BaseModel):
    """Request model for group image download endpoint."""

    image_id: UUID = Field(..., description="UUID of the images_resource to download")


class ImageDownloadGroupApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


# =============================================================================
# Video Download
# =============================================================================


class VideoDownloadGroupApiRequest(BaseModel):
    """Request model for group video download endpoint."""

    video_id: UUID = Field(..., description="UUID of the videos_resource to download")


class VideoDownloadGroupApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


# =============================================================================
# Text Download
# =============================================================================


class TextDownloadGroupApiRequest(BaseModel):
    """Request model for group text download endpoint."""

    text_id: UUID = Field(..., description="UUID of the texts_resource to download")


class TextDownloadGroupApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


# =============================================================================
# File Download
# =============================================================================


class FileDownloadGroupApiRequest(BaseModel):
    """Request model for group file download endpoint."""

    file_id: UUID = Field(..., description="UUID of the files_resource to download")


class FileDownloadGroupApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


# =============================================================================
# File Preview
# =============================================================================


class FilePreviewGroupApiRequest(BaseModel):
    """Request model for group file preview endpoint."""

    file_id: UUID = Field(..., description="UUID of the files_resource to preview")


class FilePreviewGroupApiResult(BaseModel):
    """Resolved preview info returned by the infra function."""

    preview_bytes: bytes = Field(..., description="PNG image bytes of the first page")
    upload_id: UUID = Field(..., description="UUID of the uploads_entry")


# =============================================================================
# Audio Download
# =============================================================================


class AudioDownloadGroupApiRequest(BaseModel):
    """Request model for group audio download endpoint."""

    audio_id: UUID = Field(..., description="UUID of the audios_resource to download")


class AudioDownloadGroupApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


# =============================================================================
# Call Download
# =============================================================================


class CallDownloadGroupApiRequest(BaseModel):
    """Request model for group call download endpoint."""

    call_id: UUID = Field(..., description="UUID of the calls_resource to download")


class CallDownloadGroupApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")
