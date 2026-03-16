"""Metrics entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateMetricsEntryResponse(BaseModel):
    ts: str


class CreateMetricsResponse(BaseModel):
    id: UUID


class GetMetricsResponse(BaseModel):
    id: UUID
    ts: datetime
    requests_total: int
    errors_total: int
    avg_latency_ms: float
    cpu_percent: float
    memory_bytes: int
    session_id: UUID | None
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool


class GetMetricsSearchResponse(BaseModel):
    date_hour: datetime
    sample_count: int
    avg_cpu_percent: float
    min_cpu_percent: float
    max_cpu_percent: float
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    avg_memory_bytes: int
    min_memory_bytes: int
    max_memory_bytes: int
    max_requests_total: int
    max_errors_total: int
