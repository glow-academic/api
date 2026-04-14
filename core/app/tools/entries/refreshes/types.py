"""Refresh entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateRefreshResponse(BaseModel):
    id: UUID


class GetRefreshResponse(BaseModel):
    id: UUID
    operation_key: UUID
    artifact_type: str
    target: str
    session_id: UUID
    created_at: datetime
