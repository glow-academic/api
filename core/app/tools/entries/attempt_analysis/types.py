"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAttemptAnalysisResponse(BaseModel):
    id: UUID


class GetAttemptAnalysisResponse(BaseModel):
    analysis_id: UUID
    grade_id: UUID
    content: str
    created_at: datetime
