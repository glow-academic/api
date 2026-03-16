"""Test entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateTestResponse(BaseModel):
    id: UUID


class GetTestResponse(BaseModel):
    test_id: UUID
    eval_id: UUID | None
    profile_id: UUID | None
    department_ids: list[UUID]
    test_name: str
    test_description: str
    num_invocations: int
    infinite_mode: bool
    is_dynamic: bool
    archived: bool
    test_created_at: datetime
