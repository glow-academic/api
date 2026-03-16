"""Names resource types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GetNameResponse(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool


# Backward-compat alias for service layer
NameItem = GetNameResponse
QGetNamesV4Item = GetNameResponse


class GetNamesRequest(BaseModel):
    ids: list[UUID] = Field(default_factory=list)


class GetNamesResponse(BaseModel):
    items: list[GetNameResponse] = Field(default_factory=list)


class CreateNameRequest(BaseModel):
    name: str


class CreateNameResponse(BaseModel):
    name_id: UUID
    call_id: UUID | None = None
