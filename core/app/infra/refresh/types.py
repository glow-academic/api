"""Shared Pydantic models for composable refresh responses."""

from uuid import UUID

from pydantic import BaseModel, Field


class RefreshResponse(BaseModel):
    """Standard response for composable refresh endpoints.

    Returned by all `refresh_{artifact}_client` infra functions.
    """

    success: bool
    refreshed_views: list[str]
    invalidated_tags: list[str]
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
