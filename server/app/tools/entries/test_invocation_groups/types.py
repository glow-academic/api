"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateTestInvocationGroupsResponse(BaseModel):
    id: UUID


class GetTestInvocationGroupsResponse(BaseModel):
    id: UUID
    test_invocation_id: UUID
    created_at: datetime
    updated_at: datetime
    generated: bool
    mcp: bool
    active: bool
    agent_ids: list[UUID] = []
    reasoning_level_ids: list[UUID] = []
    temperature_level_ids: list[UUID] = []
    voice_ids: list[UUID] = []
    prompt_ids: list[UUID] = []
    instruction_ids: list[UUID] = []
    tool_ids: list[UUID] = []
    quality_ids: list[UUID] = []
    modality_ids: list[UUID] = []
