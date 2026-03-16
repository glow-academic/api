"""Benchmark entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateBenchmarkResponse(BaseModel):
    id: UUID


class GetBenchmarkResponse(BaseModel):
    benchmark_id: UUID
    use_groups: bool
    dynamic: bool
    eval_ids: list[UUID]
    profile_ids: list[UUID]
    department_ids: list[UUID]
    invocation_entry_ids: list[UUID]
    created_at: datetime
    updated_at: datetime
    active: bool
