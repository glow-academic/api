"""Test invocation bridge entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateTestInvocationBridgeResponse(BaseModel):
    test_invocation_id: UUID
    invocation_id: UUID


class GetTestInvocationBridgeResponse(BaseModel):
    test_invocation_id: UUID
    invocation_id: UUID
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
    session_id: UUID
