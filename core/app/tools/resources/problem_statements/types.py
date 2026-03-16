"""Types for problem_statements resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetProblemStatementResponse(BaseModel):
    id: UUID
    name: str
    problem_statement: str
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
