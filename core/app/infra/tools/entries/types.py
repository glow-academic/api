"""Tool setup infra types — handcrafted, co-located with handler."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel


class CreateToolSetupResponse(BaseModel):
    result_id: UUID | None = None  # Canonical ID of the created resource/entry
    result: Any | None = None
    run_id: UUID
    call_id: UUID | None
    call_upload_id: UUID | None = None  # Receipt file UUID (filename for the .json)
    message_id: UUID
    text_id: UUID
    text_upload_junction_id: UUID
    call_upload_junction_id: UUID | None
    message_text_upload_junction_id: UUID
    message_call_upload_junction_id: UUID | None
