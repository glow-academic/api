"""Tool setup infra types — handcrafted, co-located with handler."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel


class CreateToolSetupResponse(BaseModel):
    result_id: UUID | None = None  # Canonical ID of the created resource/entry
    result: Any | None = None
    # Original exception raised by the tool_fn (preserved so callers can
    # re-raise the real type — HTTPException, CsvParseError, … — instead of a
    # generic Exception that flattens 4xx contracts to 500). ``Any`` so Pydantic
    # stores the exception object as-is without validation.
    error: Any | None = None
    run_id: UUID
    call_id: UUID | None
    call_upload_id: UUID | None = None  # Receipt file UUID (filename for the .json)
    message_id: UUID
    text_id: UUID
    text_upload_junction_id: UUID
    call_upload_junction_id: UUID | None
    message_text_upload_junction_id: UUID
    message_call_upload_junction_id: UUID | None
