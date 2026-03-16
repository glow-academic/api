"""Benchmark test entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateBenchmarkTestResponse(BaseModel):
    benchmark_id: UUID
    test_id: UUID


class GetBenchmarkTestResponse(BaseModel):
    benchmark_id: UUID
    test_id: UUID
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
    session_id: UUID
