"""Practice entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreatePracticeResponse(BaseModel):
    id: UUID


class GetPracticeResponse(BaseModel):
    id: UUID
    simulation_ids: list[UUID]
    cohort_ids: list[UUID]
    department_ids: list[UUID]
    profile_ids: list[UUID]
    chat_ids: list[UUID]
    scenario_ids: list[UUID]
    created_at: datetime
    updated_at: datetime
    active: bool
