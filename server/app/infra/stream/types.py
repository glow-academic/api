"""Shared API types for centralized event delivery."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EventEnvelope(BaseModel):
    """Transport-level event shape exposed by generic delivery endpoints."""

    id: str
    event_type: str
    artifact: str
    operation: str
    created_at: datetime
    entity_id: UUID | None = None
    call_id: UUID | None = None
    tool_id: UUID | None = None
    payload: dict = Field(default_factory=dict)
