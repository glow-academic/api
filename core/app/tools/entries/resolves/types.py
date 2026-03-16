"""Resolves entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateResolveResponse(BaseModel):
    id: UUID


class GetResolveResponse(BaseModel):
    id: UUID
    created_at: datetime
    generated: bool
    mcp: bool
    active: bool
    problem_id: UUID
    resolved: bool
    call_id: UUID | None
