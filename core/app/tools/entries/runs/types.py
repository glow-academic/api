"""Runs entry types — handcrafted, co-located with handler."""

from uuid import UUID

from pydantic import BaseModel


class CreateRunResponse(BaseModel):
    id: UUID


class GetRunResponse(BaseModel):
    id: UUID
    session_id: UUID
    group_id: UUID
    mcp: bool
    generated: bool
