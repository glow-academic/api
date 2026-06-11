"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAttemptCompletionResponse(BaseModel):
    id: UUID
    # True iff the row is an MV-visible (hard) completion. A soft proposal that
    # only occupies the unique slot, or a conflict that did not supersede a
    # dormant proposal, reports ``active=False`` so the caller can tell the
    # completion did NOT actually take effect (B1).
    active: bool = True


class GetAttemptCompletionResponse(BaseModel):
    id: UUID
    attempt_id: UUID
    stop: bool
    error: bool
    message: str
    session_id: UUID | None = None
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
