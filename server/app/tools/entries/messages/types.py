"""Messages entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateMessageResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the created message")
    created_at: datetime = Field(..., description="Creation timestamp")


class GetMessageResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the message")
    run_id: UUID = Field(..., description="UUID of the parent run")
    role: str = Field(..., description="Message role (e.g. user, assistant)")
    created_at: datetime = Field(..., description="Creation timestamp")
    active: bool = Field(..., description="Whether the message is active")
    mcp: bool = Field(..., description="Whether the message is from MCP")
    generated: bool = Field(..., description="Whether the message was AI-generated")
    agent_ids: list[UUID] = Field(default_factory=list, description="Associated agent UUIDs")


class SearchMessageResponse(BaseModel):
    message_id: UUID = Field(..., description="UUID of the message")
    run_id: UUID = Field(..., description="UUID of the parent run")
    role: str = Field(..., description="Message role (e.g. user, assistant)")
    message_created_at: datetime = Field(..., description="Message creation timestamp")
    text_upload_ids: list[UUID] = Field(..., description="UUIDs of text uploads")
    audio_upload_ids: list[UUID] = Field(..., description="UUIDs of audio uploads")
    image_upload_ids: list[UUID] = Field(..., description="UUIDs of image uploads")
    video_upload_ids: list[UUID] = Field(..., description="UUIDs of video uploads")
    file_upload_ids: list[UUID] = Field(..., description="UUIDs of file uploads")
    call_upload_ids: list[UUID] = Field(..., description="UUIDs of call uploads")
