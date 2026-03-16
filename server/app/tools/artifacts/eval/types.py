"""Eval artifact types — tool layer."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GetEvalsResponse(BaseModel):
    id: UUID = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    generated: bool = Field(..., description="Whether eval was auto-generated")
    mcp: bool = Field(..., description="Whether eval uses MCP")
    active: bool = Field(..., description="Whether eval is active")
    # Junction IDs — None when not requested
    name_ids: list[UUID] | None = Field(None, description="Associated name junction IDs")
    description_ids: list[UUID] | None = Field(None, description="Associated description junction IDs")
    department_ids: list[UUID] | None = Field(None, description="Associated department junction IDs")
    flag_ids: list[UUID] | None = Field(None, description="Associated flag junction IDs")
    model_ids: list[UUID] | None = Field(None, description="Associated model junction IDs")
    model_flag_ids: list[UUID] | None = Field(None, description="Associated model flag junction IDs")
    model_position_ids: list[UUID] | None = Field(None, description="Associated model position junction IDs")
    model_rubric_ids: list[UUID] | None = Field(None, description="Associated model rubric junction IDs")
    eval_ids: list[UUID] | None = Field(None, description="Associated eval junction IDs")


class CreateEvalResponse(BaseModel):
    id: UUID = Field(..., description="ID of the created eval")


class UpdateEvalResponse(BaseModel):
    id: UUID = Field(..., description="ID of the updated eval")


class DeleteEvalsResponse(BaseModel):
    deleted_ids: list[UUID] = Field(..., description="UUIDs of deleted evals")
