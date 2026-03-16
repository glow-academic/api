"""Health entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateHealthResponse(BaseModel):
    id: UUID


class GetHealthResponse(BaseModel):
    date_hour: datetime
    service: str
    check_count: int
    ok_count: int
    fail_count: int
    uptime_percent: float
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    latest_ok: bool
    latest_error: str
