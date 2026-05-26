"""Shared Pydantic models for composable refresh responses."""

from uuid import UUID

from pydantic import BaseModel, Field


class RefreshApiRequest(BaseModel):
    """Optional request body for artifact refresh endpoints.

    All fields optional so a bare ``POST /<artifact>/refresh`` (no body) still
    works. ``idempotency_key`` drives the replay gate; ``soft``/``accept`` use the
    lightweight ``enqueue_refreshes`` lifecycle (record intent without enqueuing;
    ack enqueues) — safe at HTTP (no soft_calls_entry FK; keyed by operation_key).
    """

    idempotency_key: UUID | None = Field(None, description="Idempotency key — safe-retry replay; ack of a staged (held) refresh when sent with accept")
    soft: bool = Field(False, description="Stage the refresh as held (recorded, not enqueued); accept releases it")
    accept: bool | None = Field(None, description="Accept (enqueue) or reject a held refresh. Only meaningful with idempotency_key")


class RefreshResponse(BaseModel):
    """Standard response for composable refresh endpoints.

    Returned by all `refresh_{artifact}_client` infra functions.
    """

    success: bool
    refreshed_views: list[str]
    invalidated_tags: list[str]
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
