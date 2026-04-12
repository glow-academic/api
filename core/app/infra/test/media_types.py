"""Test media types — request/result models for download operations.

TODO: Add image_download, video_download, audio_download, file_download,
      file_preview as modalities expand beyond text and calls.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class TextDownloadTestApiRequest(BaseModel):
    text_id: UUID = Field(..., description="UUID of the text resource to download")


class TextDownloadTestApiResult(BaseModel):
    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


class CallDownloadTestApiRequest(BaseModel):
    call_id: UUID = Field(..., description="UUID of the call resource to download")


class CallDownloadTestApiResult(BaseModel):
    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")
