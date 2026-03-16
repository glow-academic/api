"""Tokens entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateTokenResponse(BaseModel):
    id: UUID


class GetTokenResponse(BaseModel):
    id: UUID
    created_at: datetime
    generated: bool
    mcp: bool
    active: bool
    run_id: UUID
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    session_id: UUID | None
