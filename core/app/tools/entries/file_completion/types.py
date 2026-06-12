"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateFileCompletionResponse(BaseModel):
    id: UUID
    # True iff the row is an MV-visible (hard) completion. A soft proposal or a
    # conflict that did not supersede a dormant proposal reports ``active=False``
    # so the caller can tell the completion did NOT take effect (C1-B).
    active: bool = True


class GetFileCompletionResponse(BaseModel):
    id: UUID
    file_id: UUID
    stop: bool
    error: bool
    message: str
    session_id: UUID | None = None
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
