"""Entry types — handcrafted, co-located with handler."""

from uuid import UUID

from pydantic import BaseModel


class CreateAttemptMessageTreeResponse(BaseModel):
    parent_id: UUID
    child_id: UUID


class GetAttemptMessageTreeResponse(BaseModel):
    message_id: UUID
    branch_path: list[UUID]
    depth: int
