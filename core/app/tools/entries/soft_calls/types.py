"""Soft calls entry types — handcrafted, co-located with handler."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class CreateSoftCallResponse(BaseModel):
    id: UUID


class GetSoftCallResponse(BaseModel):
    id: UUID
    call_id: UUID
    artifact: str
    operation: str
    status: str
    artifact_id: UUID
    patch: dict[str, Any] | None
    created_at: datetime
